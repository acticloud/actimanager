#!/usr/bin/env python3

import logging, numpy, queue, sched, sys, threading, time, os
from novaclient import client

_RETRIES = 5
_RETRY_WAIT = 5

def get_env_vars(items):
    ret = {}
    for (k, v, d) in items:
        ret[k] = os.getenv(v, d)
    return ret
def get_creds(extra_vars=None):
    creds = (
            ("version", "OS_COMPUTE_API_VERSION", ""),
            ("username", "OS_USERNAME", ""),
            ("password", "OS_PASSWORD", ""),
            ("project_id", "OS_PROJECT_ID", ""),
            ("auth_url", "OS_AUTH_URL", ""),
            ("project_domain_id", "OS_PROJECT_DOMAIN_ID", ""),
            ("project_domain_name", "OS_PROJECT_DOMAIN_NAME", ""),
            ("user_domain_id", "OS_USER_DOMAIN_ID", ""),
            ("user_domain_name", "OS_USER_DOMAIN_NAME", ""),)
    if extra_vars:
        creds.append(extra_vars)
    return get_env_vars(creds)

class Demo(object):
    def __init__(self, logger=None):
        self._logger = logger
        if not self._logger:
            self._logger = logging.getLogger(__name__)
            self._logger.addHandler(logging.StreamHandler())
            self._logger.setLevel(logging.INFO)

        params = (
            ("image_id", "IMAGE_ID", "16911ffb-eb74-45d1-a524-4fd430bdf46b"),
            ("flavor_id", "FLAVOR_ID", "339aca26-6650-4838-a421-5c883810be8e"),
            ("silver_group_id", "SILVER_GROUP_ID",
             "ed5ac2ad-0e14-4260-8cd7-f0ddea410717"),
            ("gold_group_id", "GOLD_GROUP_ID",
             "e942edc2-444e-4054-8632-9394d53432c4"),
            ("num_instances", "INSTANCES", 16),
            ("max_batch", "BATCH", 4),
            ("max_delay", "DELAY", 10),
            ("silver_prob", "SILVER_PROB", 0.7),
            ("prefix", "PREFIX", "demo"),)

        self.params = common.get_env_vars(params)
        self._nova = client.Client(logger=self._logger, **common.get_creds())
        self._scheduler = sched.scheduler(time.time, time.sleep)
        self._queue = queue.Queue()

    def _delete_instances(self, instances):
        if not instances:
            return

        for instance in instances:
            self._logger.info("Deleting instance {}...".format(instance.name))
            instance.delete()

        retries = _RETRIES

        while retries > 0:
            done = True

            for instance in instances:
                try:
                    instance.get()
                    self._logger.info("Waiting for instance {} to be "
                                      "removed...".format(instance.name))
                    retries -= 1
                    done = False
                    time.sleep(_RETRY_WAIT)
                    break
                except Exception as e:
                    if getattr(e, "http_status", None) == 404:
                        continue
                    else:
                        raise

            if done:
                break

    def cleanup(self):
        prefix = r"^{}-".format(self.params["prefix"])
        instances = self._nova.servers.list(search_opts={"name": prefix})
        self._delete_instances(instances)

    def _wait_for_ready_instances(self, instances):
        nova = self._nova
        retries = _RETRIES

        while retries > 0:
            done = True

            for instance in instances:
                status = nova.servers.get(instance.id).status

                if status == "BUILD":
                    self._logger.info("Waiting for instance {} to become "
                                      "active...".format(instance.name))
                    retries -= 1
                    done = False
                    time.sleep(_RETRY_WAIT)
                    break

                if status == "ERROR":
                    self._logger.warn("Found instance {} with error "
                                      "status...".format(instance.name))

            if done:
                break

    def _worker(self):
        q = self._queue

        while True:
            instance = q.get()
            if instance is None:
                break

            self._wait_for_ready_instances((instance, ))
            if numpy.random.rand() < 0.5:  # delete ~half the instances
                delay = numpy.random.randint(10, 60)
                self._logger.info("Scheduling instance {} removal in {} "
                                  "seconds...".format(instance.name, delay))
                self._scheduler.enter(delay, 1, self._delete_instances,
                                      ((instance, ), ))
                self._scheduler.run()

            q.task_done()

    def run(self):
        params = self.params
        nova = self._nova

        fl = nova.flavors.get(params["flavor_id"])
        img = nova.glance.find_image(params["image_id"])

        gold_group_id = params["gold_group_id"]
        silver_group_id = params["silver_group_id"]
        num_instances = int(params["num_instances"])
        prob = float(params["silver_prob"])

        gold_group = nova.server_groups.get(gold_group_id)
        silver_group = nova.server_groups.get(silver_group_id)

        group_name = lambda g: gold_group.name if g == gold_group_id else silver_group.name

        groups = numpy.random.choice([silver_group_id, gold_group_id],
                                     num_instances, [prob, 1 - prob])
        self._logger.info("Generated weighted random instance grouping "
                          "distribution: {}".format([group_name(g) for g in
                                                     groups]))

        worker_threads = []
        for i in range(num_instances):
            t = threading.Thread(target=self._worker)
            t.start()
            worker_threads.append(t)

        cnt = 0
        instances = []
        while cnt < num_instances:
            batch = numpy.random.randint(1, min(params["max_batch"],
                                                num_instances - cnt) + 1)
            delay = numpy.random.randint(1, params["max_delay"] + 1)

            for i in range(batch):
                name = "{}-{}".format(params["prefix"], cnt + i)
                instance = (nova.servers.create(name, flavor=fl, image=img,
                                                scheduler_hints={"group": groups[cnt + i]},
                                                nics="none"))
                instances.append(instance)
                self._logger.info("Creating {2} instance "
                                  "{0}/{1}...".format(cnt + i + 1,
                                                      num_instances,
                                                      group_name(groups[cnt + i])))
                self._queue.put(instance)

            cnt += batch
            if cnt < num_instances:
                self._logger.info("Waiting {} seconds...".format(delay))
                time.sleep(delay)

        self._queue.join()

        for _ in range(num_instances):
            self._queue.put(None)

        for t in worker_threads:
            t.join()


def main():
    demo = Demo()

    if "run" not in sys.argv and "cleanup" not in sys.argv:
        logging.warn("Exiting, no actions requested...")
        return 0

    if "run" in sys.argv:
        demo.run()

    if "cleanup" in sys.argv:
        demo.cleanup()


if __name__ == '__main__':
    sys.exit(main())
