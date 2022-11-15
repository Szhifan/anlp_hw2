
import re 
import math 
import numpy as np 
report=open("report.txt","r").readlines()
regex=r"([a-zA-Z].*[a-zA-Z])\s+((\d+\.)?\d+)\s+((\d+\.)?\d+)\s+((\d+\.)?\d+)\s+((\d+\.)?\d+)"
precisions=0
recalls=0
fscores=0
for line in report:
    precision=float(re.search(regex,line).group(2)) 
    recall=float(re.search(regex,line).group(3))
    fscore=float(re.search(regex,line).group(4))
    precisions+=precision/len(report)
    recalls+=recall/len(report)
    fscores+=fscore/len(report)
print(precisions)
print(recalls)
print(fscores)

