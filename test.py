def get_correct_labels(prev:str,cur):
    
   

    if  (cur.startswith("B") and cur[1:]==prev[1:]):# when the BIO condition is violated when the current tag is B
        print('123112')
        
    return cur #If BIO condition nis not violated. 
bios=["O","B-date_period","O","B-date_to","B-date_to","B-date"]
n=len(bios)
for i in range(1,n):
    print(bios[i-1],bios[i])
    get_correct_labels(bios[i-1],bios[i])