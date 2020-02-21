#!/usr/bin/env python
import sys    
import pandas as pd  
import numpy as np  
from sklearn import preprocessing 
from sklearn.externals import joblib
from sklearn.svm import SVC

dataset = pd.read_csv('data_3noise.csv') 

x_n = dataset.drop(dataset.columns[[0,1,4,5,6,7,9,10]], axis=1) # for noise keep 'l3_mpki', 'l3_acpki', 'l3_mpki_pros_l3_acpki'
x_s = dataset.drop(dataset.columns[[0,1,5,6,8,9,10]], axis=1) # for sensitivity keep 'l3_mpki', 'l3_acpki', 'mem_bwdth', 'l2_miss_stalls_pros_tot_cycles'

scaler_n = preprocessing.StandardScaler().fit(x_n) # necessary 
scaler_s = preprocessing.StandardScaler().fit(x_s) # necessary 

test_data = pd.read_csv('spec2006-perfcount-cmask-percore-results-parsed-totalbw.txt') # .csv file with benchmarks to test
#x_test = test_data.drop(test_data.columns[[]], axis=1) # insert which columns to drop (see the aforementioned metrics kept in the respective train set) 
x_test_n = test_data.drop(test_data.columns[[0,1,4,5,6,7,9,10]], axis=1) # for noise keep 'l3_mpki', 'l3_acpki', 'l3_mpki_pros_l3_acpki'
x_test_s = test_data.drop(test_data.columns[[0,1,5,6,8,9,10]], axis=1) # for sensitivity keep 'l3_mpki', 'l3_acpki', 'mem_bwdth', 'l2_miss_stalls_pros_tot_cycles'
names = test_data['name'] # keep column with benchmark names

inp_n = scaler_n.transform(x_test_n) # necessary
inp_s = scaler_s.transform(x_test_s) # necessary

#model = joblib.load('/path/to/classifier/file') # load respective classifier
#model = joblib.load('3noise_rbf_c10_g1_3_acpki_features.pkl') # load respective classifier
#with open('3noise_rbf_c10_g1_3_acpki_features.pkl', 'r') as fo:
#    joblib.load(fo)

model_n = SVC(kernel='rbf', C=10, gamma=1, probability=True) # for noise
y_n = dataset['noise']
model_s = SVC(kernel='rbf', C=2, gamma=1, probability=True) # for sensitivity
y_s = dataset['sensitivity']

x_scaled_n = scaler_n.transform(x_n)
model_n.fit(x_scaled_n, y_n)
x_scaled_s = scaler_s.transform(x_s)
model_s.fit(x_scaled_s, y_s)

test_pred_n = model_n.predict(inp_n)	# make predictions
prob_n = model_n.predict_proba(inp_n)	# compute score of each class (certainty of the classifier)
test_pred_s = model_s.predict(inp_s)	# make predictions
prob_s = model_s.predict_proba(inp_s)	# compute score of each class (certainty of the classifier)

out = open('output-results.txt', 'w+')
for i in range(len(names)):
	out.write((np.array(names))[i]+','+str(test_pred_n[i])+','+str(test_pred_s[i])+'\n')
	#out_n.write('predicted class: '+str(test_pred_n[i])+'\n')
	#out_n.write(str(prob_n[i])+'\n')
out.close()
