import os                       # for os.listdir and os.environ
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'    # suppress Tensorflow warnings
import numpy as np
from nltk.corpus import stopwords
import re                       # for removing punctuations
import sys                      # for sys.stdin.readline()
from collections import defaultdict # for default value of word-vector dictionary
import pickle
import h5py

import tensorflow as tf

# Keras deep learning library
from keras.models import Sequential
from keras.layers.recurrent import LSTM
from keras.layers import Dense, Activation
from keras.optimizers import Adam, RMSprop, SGD
from keras.callbacks import Callback
from keras import backend as K

# Load the trained model
#model = keras.models.load_weights('Keras-NN_weigts.h5')
path_to_glove = "wiki-news-300d-1M.vec"
GLOVE_SIZE = 300
batch_size = 512
num_classes = 10
times_steps = 8                        # time steps for RNN.  This number should be same as fixed_seq_len below
fixed_seq_len = times_steps

# 10 categories:
categories = ["matrimonial-rights", "separation", "divorce", "after-divorce", "divorce-maintenance",
    "property-on-divorce", "types-of-marriages", "battered-wife-and-children", "Harmony-House", "divorce-mediation"]

# =================== Read unique words list & word2vec map ======================

pickle_off = open("prepared-data/unique-words.pickle", "rb")
word_list = pickle.load(pickle_off)

pickle_off = open("prepared-data/word2vec-map.pickle", "rb")
word2vec_map = pickle.load(pickle_off)

# set default value = zero vector, if word not found in dictionary
zero_vector = np.asarray([0.0] * GLOVE_SIZE, dtype='float32')
word2vec_map = defaultdict(lambda: zero_vector, word2vec_map)

# =================== Try to use continuous-training mode ======================

filenames = os.listdir("laws-TXT/family-laws")
in_file = open("laws-TXT/family-laws/" + filenames[0], encoding="utf-8")      # try the 1st file, for now

remainders = []

def get_next_word_vec():
    global remainders
    while True:
        if len(remainders) > 0:
            head = remainders[0]
            remainders = remainders[1:]
            if head not in stopwords.words('english'):
                return word2vec_map[head]
        else:
            try:
                line = next(in_file)
                line = re.sub(r"[^\w-]", " ", line)             # strip punctuations except hyphen
                line = re.sub(u"[\u4e00-\u9fff]", " ", line)    # strip Chinese
                line = re.sub(r"\d", " ", line)                 # strip numbers
                line = re.sub(r"-+", "-", line)                 # reduce multiple --- to -
                remainders = line.lower().split()
            except:
                print("***** reached EOF")
                exit(0)

# =================== Prepare batch data ============================

def get_sentence_batch(batch_size):
    data = [[get_next_word_vec()
                for _ in range(fixed_seq_len)]
                    for _ in range(batch_size)]
    return data

# =========== define objective function for unsupervised competitive learning ==========

    # y_true can be ignored
    """
    threshold = min(np.partition(y_pred, -3)[-3 :])    # last 3 elements would be biggest
    loss = np.zeros(10)
    for i in range(0,10):
        y = y_pred[i]
        if y > threshold:                              
            loss[i] = 1.0 - y                          # if it is the winner, ideal value = 1.0
        else:
            loss[i] = y                                # if it is loser, ideal value = 0.0
    """

def bingo_loss(y_true, y_pred):
    alpha = 0.1
    y2 = alpha * (1 - y_pred)
    values, indices = tf.nn.top_k(y_pred, k = 3)
    min_val = tf.reduce_min(values, axis = 1)
    min_vals = tf.reshape(tf.tile(min_val, [10]), [-1, 10])
    loss = tf.where(tf.greater(y_pred, min_vals), y2, alpha * y_pred)
    return loss

# ========= define input, output, and NN structure - need to modify =========
#define the optimizer here
opt = Adam(lr=0.0067, beta_1=0.9, beta_2=0.999, epsilon=1e-08)

#how many epoch to train
nb_epochs = 30
x_train = np.array(get_sentence_batch(batch_size))
x_test = np.array(get_sentence_batch(batch_size))
# generate a 2D array
y_train = np.random.rand(512,10)
##print (type(x_train))
##print (len(x_train))
##print (len(x_train[0]))
##print (len(x_train[0][0]))
print('Build NN model ...')
model = Sequential() # this is the first layer of keras
model.add(LSTM(units=128, dropout=0.05, recurrent_dropout=0.35, return_sequences=True, input_shape=[times_steps, GLOVE_SIZE]))
model.add(LSTM(units=64, dropout=0.05, recurrent_dropout=0.35, return_sequences=False))
model.add(Dense(units=num_classes, activation='softmax'))

# compile the model -- define loss function and optimizer
print("Compiling ...")
# loss type of cateforical crossentropy is good to classification model
model.compile(loss=bingo_loss, optimizer=opt, metrics=['accuracy'])
model.summary()
model.fit(x_train, y_train , batch_size=batch_size, epochs=nb_epochs)

# testing
print("\nTesting ...")

score, accuracy = model.evaluate(x_test, y_train, batch_size=batch_size, verbose=1)
print("Test loss:  ", score)
print("Test accuracy:  ", accuracy)

# Save the model #
model.save('Keras-NN-training2.h5')

# =================== Process a single query =================== #
try:
        while True:
                print("----------------------------\n? ", end = '')
                sys.stdout.flush()
                query = sys.stdin.readline()
                query = re.sub(r'[^\w\s-]',' ', query)	# remove punctuations except hyphen
                query_words = []
                for word in query.lower().split():		# convert to lowercase
                        if word not in stopwords.words('english'):	# remove stop words
                                query_words.append(word)

                # ===== convert query to word-vectors
                query_vectors = []
                glove_file = open(path_to_glove, "r",encoding = "utf-8")
                count_all_words = 0
                entry_number = 0
                for word_entry in glove_file:
                        vals = word_entry.split()
                        word = str(vals[0])
                        entry_number += 1
                        if word in query_words:
                                count_all_words += 1
                                print(count_all_words, word, end = '\r')
                                coefs = np.asarray(vals[1:], dtype='float32')
                                coefs /= np.linalg.norm(coefs)
                                word2vec_map[word] = coefs
                        if count_all_words == len(word_list) - 1:
                                break
                        if entry_number > 50000:
                                # took too long to find the words
                                break

                # ===== make the query length to be (32) = times_steps size
                long_enough = False
                while not long_enough:
                        for word in query_words:
                                query_vectors.append(word2vec_map[word])
                                if len(query_vectors) == times_steps:
                                        long_enough = True
                                        break

        #=========================  prediction ==============================#
                prediction = model.predict(np.expand_dims(query_vectors, axis=0))
                #result = np.argmax(prediction)          #get the max column
                result = []
                for i in range(len(prediction)):
                        result.append(categories[np.argmax(prediction[i])])
                print("\n ⟹  category: ", result[0])
                
except KeyboardInterrupt:
    pass




