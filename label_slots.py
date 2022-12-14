import argparse
import json
import math
import os
import sklearn.linear_model
import spacy
import sys
import utils
from collections import defaultdict
import numpy as np 
DATA_DIR = "data"
TRAINING_FILE = "training_data.json"
VALIDATION_FILE = "validation_data.json"
TEST_FILE="test_data.json" 

spacy.tokens.token.Token.set_extension("bio_slot_label", default="O")
def tag2vec(tag):
    """ 
    Args: 
        tag: the spacy POS tag of a token 
    Returns: 
        np.array: a binary vector representing the pre/absence of a POS tag. 
    
    """
    tag_list=["VB","CD","IN","JJ","NN","VB"]
    #we belive these POS tags are most the relevant to our task. 
    dict={i:0 for i in tag_list}
    try: 
        dict[tag[:2]]+=1 
    except KeyError: 
        pass
    return np.array(list(dict.values())) 
def _predict_tag_mle(token, model_parameters):
    """
    Predict most-frequent-tag baseline, i.e. argmax_{<tag>} P(<tag> | <word>).

    Args:
        token (spacy.tokens.Token): token whose tag we want to predict
        model_parameters (dict): a mapping token from most frequent tag, and an unknown word tag

    Returns:
        (List(Tuple(str,float))): a list of (tag, logprob) pairs, sorted from most to least probable
    """
    if token.text in model_parameters['per_word_tag_mle']:
        return model_parameters['per_word_tag_mle'][token.text]
    return model_parameters['unknown_word_distribution']


def train_tag_mle(data):
    """
    Train an unsmoothed MLE model P(<tag> | <word>).

    Args:
        data: data in NLU++ format imported from JSON, with spacy annotations.

    Returns:
        Callable: a function that returns a sorted distribution over tags, given a word.
    """
    token_count = 0
    word_tag_count = defaultdict(lambda: defaultdict(int))
    for sample in data:
        for token in sample['annotated_text']:
            word_tag_count[token.text][token._.bio_slot_label] += 1
            token_count += 1
  
    per_word_tag_mle = {}
    for word, tag_count_pairs in word_tag_count.items():
        word_count = sum(tag_count_pairs.values())
        tag_logprob_pairs = [(tag, math.log(tag_word_count / word_count)) for (tag, tag_word_count) in tag_count_pairs.items()]
        sorted_tag_logprob_pairs = sorted(tag_logprob_pairs, key=lambda tag_logprob_pair: -tag_logprob_pair[1]) 
        per_word_tag_mle[word] = sorted_tag_logprob_pairs
    # print("#"*100)
    # print(per_word_tag_mle["night"])
    model_parameters = {
        'per_word_tag_mle': per_word_tag_mle,
        # Assign O for unknown words with prob 1
        # but since we are using log probs -> log(1) = 0.
        'unknown_word_distribution': [('O', 0.0)]
    }

    print(f'> Finished training most frequent tag model on {token_count} tokens')
    return lambda token: _predict_tag_mle(token, model_parameters)

def _predict_tag_logreg(tok_vec, model, tags):
    """
    Predict tag according to logistic regression on word embedding

    Args:
        data: data in NLU++ format impored from JSON, with spacy annotations.
    
    Returns:
        (List(Tuple(str,float))): distribution over tags, sorted from most to least probable
    """
 
    log_probs = model.predict_log_proba([tok_vec])[0]
    distribution = [tag_logprob_pair for tag_logprob_pair in zip(tags, log_probs)]
    sorted_distribution = sorted(distribution, key=lambda tag_logprob_pair: -tag_logprob_pair[1])
    return sorted_distribution

def train_tag_logreg(data):
    """
    Train a logistic regression model for p(<tag> | <word embedding>).
    
    Args:
        data: data in NLU++ format imported from JSON, with spacy annotations.
    Returns:
        Callable: a function that returns a (sorted) distribution over tags, given a word.
    """
    token_count = 0
    train_X = [] 
    train_y = []
    bio_tags = set(['O'])

    for sample in data:
        for token in sample['annotated_text']:
            bio_tags.add(token._.bio_slot_label)

    bio_tags = sorted(bio_tags)
    
    bio_tag_map = {tag: idx for idx, tag in enumerate(bio_tags)}
    
    ################################################################
    ### TODO: Write code to set train_X, train_y, and token_count

    for sample in data:
        n=len(sample["annotated_text"])
        for i in range(n):
            tag=sample["annotated_text"][i].tag_  #extract the POS tag of each token 
            token_count+=1 
            if n>2: #only average the neighboring vectors if the sentence contains more than two tokens 
                if i==0: #add the next word vector at the start of the sentence 
                    vec=(sample["annotated_text"][i].vector+
                    sample["annotated_text"][i+1].vector)/2 
                elif 0<i<n-1: #add the surrounding word vector if neither at the start nor end 
                    vec=(sample["annotated_text"][i].vector+
                        sample["annotated_text"][i+1].vector+
                        sample["annotated_text"][i-1].vector
                    )/3
                else: #add the previous word vector if at the end of the sentence 
                    vec=(sample["annotated_text"][i].vector+
                    sample["annotated_text"][i-1].vector)/2
            else: 
                vec=sample["annotated_text"][i].vector 
            vec=np.concatenate([vec,tag2vec(tag)]) 
            #concatenate the averaged word vector and the POS tag vector. 
            train_X.append(vec) 
            train_y.append(sample["annotated_text"][i]._.bio_slot_label)

    print(f'> Training logistic regression model on {token_count} tokens')
    model = sklearn.linear_model.LogisticRegression(multi_class='multinomial', solver='newton-cg').fit(train_X, train_y)
    print('> Finished training logistic regression')
    return lambda tok_vec: _predict_tag_logreg(tok_vec, model, bio_tags)


def predict_independent_tags(tag_predictor, data):
    '''
    Predict tags independently of each other.
    
    Args:
        tag_predictor: function that predicts a tag, given a spacy token
        data: data in NLU++ format imported from JSON, with spacy annotations

    Returns:
        List(List(Str)): a list (one for each sample) of a list of tags (one for each word in the sample)

    ''' 
    predictions = []
 
    for sample in data:
  
        pred=[tag_predictor(token)[0][0] for token in sample['annotated_text']]
        
        predictions.append(pred)
        
        
        
    return predictions

def predict_bio_tags(tag_predictor, data):
    '''
    Predict tags respecting BIO tagging constraints.
    
    Args:
        tag_predictor: function that predicts a tag, given a spacy token
        data: data in NLU++ format imported from JSON, with spacy annotations

    Returns:
        List(List(Str)): a list (one for each sample) of a list of tags (one for each word in the sample)

    ''' 
    def get_correct_labels(prev:str,cur:str,cur_prob:list):
        """
        A helper function that correct the current label based on the previous label

        Args: 
            prev: the previous label 
            cur: the current label 
            cur_prob: the probability distribution of the current token. 

        Return:
            str: the correct label according to the BIO constraints. 
        """
        if (cur.startswith("I") and cur[1:]!=prev[1:]):  
#when the BIO condition is violated when the current tag is I
         
            for tp in cur_prob:
                if  tp[0].startswith("I") ^ (tp[0][1:]!=prev[1:]) : 
#either the new tag starts with I and comes from the same class as the previous one 
#or the new tag starts with B and DOESN'T come from the same class as the previous one.
#Note that the conditions between ^ must not simultaneously be false, i.e. it doesn't start with 
#I AND has the same class as previous one. Otherwise: 
# B-X,I-Y -> B-X,B-X  
                    return tp[0]
        if  cur.startswith("B") and cur[1:]==prev[1:]:
# when the BIO condition is violated when the current tag is B
            for tp in cur_prob:
                if  (tp[0].startswith("B") ^ (tp[0][1:]==prev[1:])):  
#either the new tag starts with B and doesn't come from the same class as the previous one. 
#or the new tag starts with I and come from the same class as the previous one. 
#The conditions on both sides of ^ must not simultaneously be false. 
# Otherwise:I-X,B-X -> I-X,I-Y.  
                    return tp[0] 
        return cur 
    predictions = []
    for sample in data:
        n=len(sample["annotated_text"])
        pred=[] 
        prev_label="O" 
        #initialize the start of the sequence, 
        #so that we don't need to check if I-tag is at the start of the sentence 
        for i in range(n):
            tok=sample["annotated_text"][i]  
            tag=sample["annotated_text"][i].tag_
            if n>2:
                if i==0: 
                    next_tok_vec=sample["annotated_text"][i+1].vector 
                    vec=(tok.vector+next_tok_vec)/2
                  
                elif i<n-1: 
                    next_tok_vec=sample["annotated_text"][i+1].vector
                    prev_tok_vec=sample["annotated_text"][i-1].vector 
                    vec=(next_tok_vec+prev_tok_vec+tok.vector)/3
                 
                else: 
                    prev_tok_vec=sample["annotated_text"][i-1].vector
                    vec=(prev_tok_vec+tok.vector)/2 
                    
            else: 
                vec=tok.vector

                
            vec=np.concatenate([vec,tag2vec(tag)])
            pred_prob=tag_predictor(vec)
            cur_label=pred_prob[0][0]
            cur_label=get_correct_labels(prev_label,cur_label,pred_prob)
              
            
            pred.append(cur_label)
            prev_label=cur_label
     
        predictions.append(pred)
    ################################################################
    ### TODO: Write code to predict tags, obeying BIO constraints
 

   
    return predictions

  
train = {
    'most_frequent_tag' : train_tag_mle,
    'logistic_regression' : train_tag_logreg
}
default_train = 'logistic_regression' 

predict = {
    'independent_tags' : predict_independent_tags,
    'bio_tags' : predict_bio_tags,
}
default_predict = 'bio_tags' 

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument('-t', '--train_path', 
                   help='path to training dataset in JSON format', 
                   default=os.path.join(DATA_DIR, TRAINING_FILE))
    p.add_argument('-v', '--validation_path', 
                   help='path to validation dataset in JSON format', 
                   default=os.path.join(DATA_DIR, VALIDATION_FILE))
    p.add_argument('-m', '--model',
                   help=f'type of model to use.',
                   choices=train.keys(), 
                   default=default_train)
    p.add_argument('-p', '--predictor',
                   help=f'type of prediction method to use.',
                   choices=predict.keys(),
                   default=default_predict)
                   
    p.add_argument('-f', '--full_report',
                   help=f'show complete output of tagging model on all sentences',
                   action='store_true')
    args = p.parse_args()

    with open(args.train_path) as f:
        training_data = json.load(f)
    with open(args.validation_path) as f:
        validation_data = json.load(f)


f = open("reports/test2.txt",'w')
sys.stdout = f
print("> Tokenising and annotating raw data")
nlp_analyser = spacy.load("en_core_web_sm")
utils.tokenise_annotate_and_convert_slot_labels_to_bio_tags(training_data, nlp_analyser)
utils.tokenise_annotate_and_convert_slot_labels_to_bio_tags(validation_data, nlp_analyser)

print(f'> Training model on ')
model = train[args.model](training_data)

print(f'> Predicting tags on validation set')
predictions = predict[args.predictor](model, validation_data)
if args.full_report:
    utils.visualise_bio_tags(predictions, validation_data)

utils.evaluate(predictions, validation_data)
print("#"*100)
f.close()