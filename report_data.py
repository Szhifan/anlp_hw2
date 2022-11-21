import re 
import numpy as np 
report=open("log.txt","r").readlines()
data=[]
for line in report: 
    d=re.findall(r"\s[0-9]\.[0-9]+\s",line)
    
    data.append(d)
data=np.array(data,dtype="float32")
data=np.mean(data,axis=0)
print(data)

