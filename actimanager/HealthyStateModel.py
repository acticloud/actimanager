import collections
import numpy as np
from scipy.spatial import distance
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, silhouette_samples
from sklearn.preprocessing import StandardScaler

perf_metrics = ['branches', 'branch-misses', 'cycles', 'instructions', 'context-switches',
                'cpu-migrations', 'page-faults', 'LLC-loads', 'LLC-load-misses',
                'dTLB-loads', 'dTLB-load-misses', 'mem-loads', 'mem-stores' ]

def read_file_all(inp_file):
    m_axis = []
    fp = open(inp_file)
    line = fp.readline()
    point = []
    while line:
        tokens = line.split()
        if tokens[2] in perf_metrics or tokens[3] in perf_metrics:
            if tokens[2] in perf_metrics:
                metric_name = tokens[2]
                value = float(tokens[1])
            else:
                metric_name = tokens[3]
                value = 0.0

            point.append(value)
            if (metric_name == perf_metrics[-1]):
                m_axis.append(point)
                point = []
        line = fp.readline()
    fp.close()
    return m_axis


def silhouette_sc_kmeans(train_axis, num_of_clusters):
    kmeans = KMeans(n_clusters=num_of_clusters, n_init=40)
    labels = kmeans.fit_predict(train_axis)
    return silhouette_score(train_axis, labels, metric='euclidean')


def test_ss_f(train_axis, train_labels, test_axis, test_labels, dev,
              train_metr):
    # Test
    test_ss = []
    outl_ind = []
    for x in range(len(test_axis)):
        ss_samples = silhouette_samples(
            np.concatenate((train_axis, [test_axis[x]])),
            np.concatenate((train_labels, [test_labels[x]])),
            metric='euclidean')
        test_ss.append(ss_samples[-1])
        if (ss_samples[-1] < train_metr * dev):
            outl_ind.append(x)
    return outl_ind, np.mean(test_ss)


def test_eu(train_axis, train_labels, test_axis, dev, train_metr):
    centroid = np.mean(train_axis, axis=0)

    test_md = []
    outl_ind = []
    for x in range(len(test_axis)):
        if len(test_axis.shape) > 1:
            test_md.append(distance.euclidean(test_axis[x, :], centroid))
        else:
            test_md.append(distance.seuclidean(test_axis[x], centroid))
        if (test_md[-1] * dev > train_metr):
            outl_ind.append(x)
    return outl_ind, np.mean(test_md)


def pre_c(train_axis, train_labels, num_of_clusters):
    # Remove small clusters
    count = collections.Counter(train_labels).most_common()
    print(count)
    outl_removed = 0
    c_co = 0
    condlist = [True] * len(train_axis)
    for i in range(1, num_of_clusters + 1):
		condlist = [True] * len(train_axis)
    for i in range(1, num_of_clusters + 1):
        el, co = (count[-i])
        outl_removed += co
        if outl_removed < len(train_axis) * 0.05:
            condlist = np.logical_and(
                condlist, train_labels[range(len(train_axis))] != el)
            print(el, outl_removed)
            c_co += 1
        else:
            outl_removed -= co
            break
    print("Preprocessing removed {} points from {} small clusters".format(
        outl_removed, c_co))
    return (train_axis[condlist, :], train_labels[condlist],
            num_of_clusters - c_co, outl_removed)


def pre_o(train_axis, train_labels, outl_removed, num_of_clusters, train_metr):
    # Remove outliers
    outl_ind = []
    dev = 0
    while (outl_removed < 0.1 * len(train_axis)):
        outl_removed -= len(outl_ind)
        dev += 0.1
        if num_of_clusters > 1:
            outl_ind, ss = test_ss_f(train_axis, train_labels, train_axis,
                                     train_labels, dev, train_metr)
        else:
            outl_ind, seu = test_eu(train_axis, train_labels, train_axis, dev,
                                    train_metr)
        outl_removed += len(outl_ind)
        print(outl_removed, len(train_axis))
    dev -= 0.1
    outl_removed -= len(outl_ind)
    if num_of_clusters > 1:
        outl_ind, ss = test_ss_f(train_axis, train_labels, train_axis,
                                 train_labels, dev, train_metr)
    else:
        outl_ind, seu = test_eu(train_axis, train_labels, train_axis, dev,
                                train_metr)
    outl_removed += len(outl_ind)
    train_axis = np.delete(train_axis, outl_ind, axis=0)
    train_labels = np.delete(train_labels, outl_ind, axis=0)
    print("Preprocessing removed {} outliers".format(outl_removed))
    print("Deviation was found {}".format(dev))
    return train_axis, train_labels, dev


def input_scale_pca_train(inp_file_train):
    train_axis = read_file_all(inp_file_train)
    train_axis = np.array(train_axis[10:-10])

    scaler1 = StandardScaler()
    train_axis = scaler1.fit_transform(train_axis)

    pca = PCA()
    train_axis = pca.fit_transform(train_axis)

    scaler2 = StandardScaler()
    train_axis = scaler2.fit_transform(train_axis)

    return train_axis, pca, scaler1, scaler2


def input_scale_pca_test(inp_file_test, pca, scaler1, scaler2):
    test = read_file_all(inp_file_test)
    test = np.array(test[10:-10])

    test = scaler1.transform(test)
    test = pca.transform(test)
    test = scaler2.transform(test)

    return test


def test_ss_f_dy(train_axis, train_labels, test_axis, test_labels, dev,
                 train_metr):
    # Test
    test_ss = []
    outl_ind = []
    for x in range(len(test_axis)):
        ss_samples = silhouette_samples(
            np.concatenate((train_axis, [test_axis[x]])),
            np.concatenate((train_labels, [test_labels[x]])),
            metric='euclidean')
        test_ss.append(ss_samples[-1])
        if (ss_samples[-1] < train_metr * dev):
            outl_ind.append(x)
    return outl_ind, test_ss


def test_eu_dy(train_axis, train_labels, test_axis, dev, train_metr):
    centroid = np.mean(train_axis, axis=0)

    test_md = []
    outl_ind = []
    for x in range(len(test_axis)):
        if len(test_axis.shape) > 1:
            test_md.append(distance.euclidean(test_axis[x, :], centroid))
        else:
            test_md.append(distance.seuclidean(test_axis[x], centroid))
        if (test_md[-1] * dev > train_metr):
            outl_ind.append(x)
    return outl_ind, test_md
    
def model_train(inp_file_train):
    train_axis, pca, scaler1, scaler2 = input_scale_pca_train(inp_file_train)

    # Find best number of clusters
    num_of_clusters = 2 + np.argmax(
        [silhouette_sc_kmeans(train_axis, i) for i in range(2, 10)])
    print("KMeans training with {} clusters".format(num_of_clusters))

    # Train
    model = KMeans(n_clusters=num_of_clusters, n_init=40)
    train_labels = model.fit_predict(train_axis)
    print("SS1 is {}".format(
        silhouette_score(train_axis, train_labels, metric='euclidean')))

    # Preprocessing clusters
    train_axis, train_labels, num_of_clusters, outl_removed = pre_c(
        train_axis, train_labels, num_of_clusters)

    # Retrain
    model = KMeans(n_clusters=num_of_clusters, n_init=40)
    train_labels = model.fit_predict(train_axis)
    if num_of_clusters > 1:
        train_metr = silhouette_score(
            train_axis, train_labels, metric='euclidean')
        print("SS2 is {}".format(train_metr))
    else:
        centroid = np.mean(train_axis, axis=0)
        train_md_samples = []
        covmx = np.var(train_axis, axis=0)
        mi = covmx[covmx != 0].min()
        covmx = np.where(covmx == 0, mi, covmx)
        for x in range(len(train_axis)):
            train_md_samples.append(
                distance.seuclidean(train_axis[x, :], centroid, covmx))
        train_md = np.mean(train_md_samples)
        train_metr = train_md
        print("Standrdized Euclidean distance is {}".format(train_md))

    # Preprocessing outliers
    train_axis, train_labels, dev = pre_o(
        train_axis, train_labels, outl_removed, num_of_clusters, train_metr)
    num_of_clusters = len(set(train_labels))

    # Retrain
    model = KMeans(n_clusters=num_of_clusters, n_init=40)
    train_labels = model.fit_predict(train_axis)
    if num_of_clusters > 1:
        train_metr = silhouette_score(
            train_axis, train_labels, metric='euclidean')
        print("SS3 is {}".format(train_metr))
    else:
        centroid = np.mean(train_axis, axis=0)
        train_md_samples = []
        covmx = np.var(train_axis, axis=0)
        mi = covmx[covmx != 0].min()
        covmx = np.where(covmx == 0, mi, covmx)
        for x in range(len(train_axis)):
            train_md_samples.append(
                distance.seuclidean(train_axis[x, :], centroid, covmx))
        train_md = np.mean(train_md_samples)
        # std_md = np.std(train_md_samples)
        train_metr = train_md
        print("Standrdized Euclidean distance 3 is {}".format(train_md))

    return num_of_clusters, train_axis, train_labels,\
        model, dev, train_metr, pca, scaler1, scaler2


def model_test_dy(
        train_axis, inp_file_test, num_of_clusters,
        train_labels, model, dev, train_metr,
        pca, scaler1, scaler2):
    test_axis = input_scale_pca_test(inp_file_test, pca, scaler1, scaler2)

    # Test
    if num_of_clusters > 1:
        test_labels = model.predict(test_axis)
        outl_ind, met = test_ss_f_dy(
            train_axis, train_labels, test_axis, test_labels, dev, train_metr)
    else:
        outl_ind, met = test_eu_dy(
            train_axis, train_labels, test_axis, dev, train_metr)
    return (sum(met) / len(met) < train_metr * dev)
