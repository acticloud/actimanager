# ACTiManager
ACTiManager is a novel cloud resource manager that maximizes the use of resources for typical scale-up and scale-out scenarios.

ACTiManager and all its software components have been implemented and evaluated during the EU H2020 ACTiCLOUD project (https://acticloud.eu/).

## Components

This repository is composed of the following components:

**actidb:** everything that is related to the database that ACTiManager uses for its internal workings.

**actimanager:** this folder contains the core functionality of the ACTiManager.

**common:** some utilities that are used by all the other components.

**viz:** tools that vizualize the various functionalities of ACTiManager.

**workload:** benchmarks that can be used to test and evaluate ACTiManager.

In each subfolder there is an additional README.md file that includes more detailed description and information about each component.

## Setting up ACTiManager

To setup ACTiManager on your data center the following steps are necessary:

- Setup actidb and start rabbitmq_client (see [actidb/README.md](actidb/README.md))
- Start ACTiManager external and internal (see [actimanager/README.md](actimanager/README.md))
- ***Optional***: if you want to see ACTiManager in action, check the tools provided in viz/
- ***Optional***: if you want to test and evaluate ACTiManager without having to write all the benchmarking your own, check the benchmarks we provide in workload/
- Enjoy
