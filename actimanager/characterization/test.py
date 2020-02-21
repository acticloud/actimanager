import pandas as pd  
import numpy as np  
from sklearn import preprocessing 
from sklearn.externals import joblib

# train set, needed for scaler (can be discarded afterwards)
dataset = pd.read_csv('data_3noise.csv')

# for noisy keep 'l3_mpki', 'l3_acpki', 'l3_mpki_pros_l3_acpki'
x = dataset.drop(dataset.columns[[0,1,4,5,6,7,9,10]], axis=1)
# for sensitivity keep 'l3_mpki', 'l3_acpki', 'mem_bwdth', 'l2_miss_stalls_pros_tot_cycles'
#x = dataset.drop(dataset.columns[[0,1,5,6,8,9,10]], axis=1)

# necessary 
scaler = preprocessing.StandardScaler().fit(x)

# .csv file with benchmarks to test
test_data = pd.read_csv('data_3noise.csv')

# insert which columns to drop (see the aforementioned metrics kept in the respective train set) 
x_test = test_data.drop(test_data.columns[[0,1,4,5,6,7,9,10]], axis=1)

# keep column with benchmark names
names = test_data['name']


inp = scaler.transform(x_test) # necessary

model = joblib.load('3noise_rbf_c10_g1_3_acpki_features.pkl') # load respective classifier

test_pred = model.predict(inp)	# make predictions
prob = model.predict_proba(inp)	# compute score of each class (certainty of the classifier)

out = open('output.txt', 'a+')

for i in range(len(names)):
	out.write((np.array(names))[i]+'\n')
	out.write('predicted class: '+str(test_pred[i])+'\n')
	out.write(str(prob[i])+'\n')

out.close()
