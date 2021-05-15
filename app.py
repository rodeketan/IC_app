from flask import Flask, render_template, request

import numpy as np
from numpy import array
import pandas as pd
import matplotlib.pyplot as plt
import string
import os
from PIL import Image
import glob
import pickle
from pickle import dump, load
from time import time
from keras.preprocessing import sequence
from keras.models import Sequential
from keras.layers import LSTM, Embedding, TimeDistributed, Dense, RepeatVector,\
                         Activation, Flatten, Reshape, concatenate, Dropout, BatchNormalization
from keras.optimizers import Adam, RMSprop
from keras.layers.wrappers import Bidirectional
from keras.layers.merge import add
from keras.applications.inception_v3 import InceptionV3
from keras.preprocessing import image
from keras.models import Model
from keras import Input, layers
from keras import optimizers
from keras.applications.inception_v3 import preprocess_input
from keras.preprocessing.text import Tokenizer
from keras.preprocessing.sequence import pad_sequences
from keras.utils import to_categorical


def load_doc(filename):
	# open the file as read only
	file = open(filename, 'r')
	# read all text
	text = file.read()
	# close the file
	file.close()
	return text



def load_descriptions(doc):
	mapping = dict()
	# process lines
	for line in doc.split('\n'):
		# split line by white space
		tokens = line.split()
		if len(line) < 2:
			continue
		# take the first token as the image id, the rest as the description
		image_id, image_desc = tokens[0], tokens[1:]
		# extract filename from image id
		image_id = image_id.split('.')[0]
		# convert description tokens back to string
		image_desc = ' '.join(image_desc)
		# create the list if needed
		if image_id not in mapping:
			mapping[image_id] = list()
		# store description
		mapping[image_id].append(image_desc)
	return mapping



def clean_descriptions(descriptions):
	# prepare translation table for removing punctuation
	table = str.maketrans('', '', string.punctuation)
	for key, desc_list in descriptions.items():
		for i in range(len(desc_list)):
			desc = desc_list[i]
			# tokenize
			desc = desc.split()
			# convert to lower case
			desc = [word.lower() for word in desc]
			# remove punctuation from each token
			desc = [w.translate(table) for w in desc]
			# remove hanging 's' and 'a'
			desc = [word for word in desc if len(word)>1]
			# remove tokens with numbers in them
			desc = [word for word in desc if word.isalpha()]
			# store as string
			desc_list[i] =  ' '.join(desc)




def to_vocabulary(descriptions):
	# build a list of all description strings
	all_desc = set()
	for key in descriptions.keys():
		[all_desc.update(d.split()) for d in descriptions[key]]
	return all_desc





def save_descriptions(descriptions, filename):
	lines = list()
	for key, desc_list in descriptions.items():
		for desc in desc_list:
			lines.append(key + ' ' + desc)
	data = '\n'.join(lines)
	file = open(filename, 'w')
	file.write(data)
	file.close()


def load_set(filename):
	doc = load_doc(filename)
	dataset = list()
	# process line by line
	for line in doc.split('\n'):
		# skip empty lines
		if len(line) < 1:
			continue
		# get the image identifier
		identifier = line.split('.')[0]
		dataset.append(identifier)
	return set(dataset)


# load clean descriptions into memory
def load_clean_descriptions(filename, dataset):
	# load document
	doc = load_doc(filename)
	descriptions = dict()
	for line in doc.split('\n'):
		# split line by white space
		tokens = line.split()
		# split id from description
		image_id, image_desc = tokens[0], tokens[1:]
		# skip images not in the set
		if image_id in dataset:
			# create list
			if image_id not in descriptions:
				descriptions[image_id] = list()
			# wrap description in tokens
			desc = 'startseq ' + ' '.join(image_desc) + ' endseq'
			# store
			descriptions[image_id].append(desc)
	return descriptions

def preprocess(image_path):
    # Convert all the images to size 299x299 as expected by the inception v3 model
    img = image.load_img(image_path, target_size=(299, 299))
    # Convert PIL image to numpy array of 3-dimensions
    x = image.img_to_array(img)
    # Add one more dimension
    x = np.expand_dims(x, axis=0)
    # preprocess the images using preprocess_input() from inception module
    x = preprocess_input(x)
    return x



# convert a dictionary of clean descriptions to a list of descriptions
def to_lines(descriptions):
	all_desc = list()
	for key in descriptions.keys():
		[all_desc.append(d) for d in descriptions[key]]
	return all_desc

# calculate the length of the description with the most words
def max_lengthi(descriptions):
	lines = to_lines(descriptions)
	return max(len(d.split()) for d in lines)








app=Flask(__name__)
app.config['send_file_max_age_default']=1
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/after', methods=['GET','POST'])
def after():
    file= request.files['file1']
    file.save('C:/Users/rode/Desktop/Projects/IC_app/Flickr8k_Dataset/Flicker8k_Dataset/file.jpg')

    filename = "C:/Users/rode/Desktop/Projects/IC_app/Flickr8k.token.txt"
    # load descriptions
    doc = load_doc(filename)
    # print(doc[:300])

    # parse descriptions
    descriptions = load_descriptions(doc)
    # print('Loaded: %d ' % len(descriptions))

    # clean descriptions
    clean_descriptions(descriptions)

    # summarize vocabulary
    vocabulary = to_vocabulary(descriptions)

    save_descriptions(descriptions, 'descriptions.txt')

    filename = 'C:/Users/rode/Desktop/Projects/IC_app/Flickr_8k.trainImages.txt'
    train = load_set(filename)
    # Below path contains all the images
    images = 'C:/Users/rode/Desktop/Projects/IC_app/Flickr8k_Dataset/Flicker8k_Dataset/'
    # Create a list of all image names in the directory
    img = glob.glob(images + '*.jpg')

    # Below file conatains the names of images to be used in test data
    test_images_file = 'C:/Users/rode/Desktop/Projects/IC_app/Flickr_8k.testImages.txt'
    # Read the validation image names in a set# Read the test image names in a set
    test_images = set(open(test_images_file, 'r').read().strip().split('\n'))

    # Create a list of all the test images with their full path names
    test_img = []

    for i in img: # img is list of full path names of all images
        if i[len(images):] in test_images: # Check if the image belongs to test set
            test_img.append(i) # Add it to the list of test images

    train_descriptions = load_clean_descriptions('descriptions.txt', train)

    # Load the inception v3 model
    model = InceptionV3(weights='imagenet')

    # Create a new model, by removing the last layer (output layer) from the inception v3
    model_new = Model(model.input, model.layers[-2].output)

    def encode(image):
        image = preprocess(image) # preprocess the image
        fea_vec = model_new.predict(image) # Get the encoding vector for the image
        fea_vec = np.reshape(fea_vec, fea_vec.shape[1]) # reshape from (1, 2048) to (2048, )
        return fea_vec


    encoding_test = {}
    for img in test_img:
        encoding_test[img[len(images):]] = encode(img)

    # Save the bottleneck test features to disk
    with open("C:/Users/rode/Desktop/Projects/IC_app/encoded_.pkl", "wb") as encoded_pickle:
        pickle.dump(encoding_test, encoded_pickle)

    # Create a list of all the training captions
    all_train_captions = []
    for key, val in train_descriptions.items():
        for cap in val:
            all_train_captions.append(cap)
    len(all_train_captions)

    word_count_threshold = 10
    word_counts = {}
    nsents = 0
    for sent in all_train_captions:
        nsents += 1
        for w in sent.split(' '):
            word_counts[w] = word_counts.get(w, 0) + 1

    vocab = [w for w in word_counts if word_counts[w] >= word_count_threshold]

    ixtoword = {}
    wordtoix = {}

    ix = 1
    for w in vocab:
        wordtoix[w] = ix
        ixtoword[ix] = w
        ix += 1
    vocab_size = len(ixtoword) + 1 # one for appended 0's

    max_length = max_lengthi(train_descriptions)

    # data generator, intended to be used in a call to model.fit_generator()
    def data_generator(descriptions, photos, wordtoix, max_length, num_photos_per_batch):
        X1, X2, y = list(), list(), list()
        n=0
        # loop for ever over images
        while 1:
            for key, desc_list in descriptions.items():
                n+=1
                # retrieve the photo feature
                photo = photos[key+'.jpg']
                for desc in desc_list:
                    # encode the sequence
                    seq = [wordtoix[word] for word in desc.split(' ') if word in wordtoix]
                    # split one sequence into multiple X, y pairs
                    for i in range(1, len(seq)):
                        # split into input and output pair
                        in_seq, out_seq = seq[:i], seq[i]
                        # pad input sequence
                        in_seq = pad_sequences([in_seq], maxlen=max_length)[0]
                        # encode output sequence
                        out_seq = to_categorical([out_seq], num_classes=vocab_size)[0]
                        # store
                        X1.append(photo)
                        X2.append(in_seq)
                        y.append(out_seq)
                # yield the batch data
                if n==num_photos_per_batch:
                    yield [[array(X1), array(X2)], array(y)]
                    X1, X2, y = list(), list(), list()
                    n=0
    def greedySearch(photo):
        in_text = 'startseq'
        for i in range(max_length):
            sequence = [wordtoix[w] for w in in_text.split() if w in wordtoix]
            sequence = pad_sequences([sequence], maxlen=max_length)
            yhat = model.predict([photo,sequence], verbose=0)
            yhat = np.argmax(yhat)
            word = ixtoword[yhat]
            in_text += ' ' + word
            if word == 'endseq':
                break
        final = in_text.split()
        final = final[1:-1]
        final = ' '.join(final)
        return final

    glove_dir = 'C:/Users/rode/Desktop/Projects/IC_app/glove/'
    embeddings_index = {} # empty dictionary
    f = open(os.path.join(glove_dir, 'glove.6B.200d.txt'), encoding="utf-8")

    for line in f:
        values = line.split()
        word = values[0]
        coefs = np.asarray(values[1:], dtype='float32')
        embeddings_index[word] = coefs
    f.close()

    embedding_dim = 200

    # Get 200-dim dense vector for each of the 10000 words in out vocabulary
    embedding_matrix = np.zeros((vocab_size, embedding_dim))

    for word, i in wordtoix.items():
        #if i < max_words:
        embedding_vector = embeddings_index.get(word)
        if embedding_vector is not None:
            # Words not found in the embedding index will be all zeros
            embedding_matrix[i] = embedding_vector

    inputs1 = Input(shape=(2048,))
    fe1 = Dropout(0.5)(inputs1)
    fe2 = Dense(256, activation='relu')(fe1)
    inputs2 = Input(shape=(max_length,))
    se1 = Embedding(vocab_size, embedding_dim, mask_zero=True)(inputs2)
    se2 = Dropout(0.5)(se1)
    se3 = LSTM(256)(se2)
    decoder1 = add([fe2, se3])
    decoder2 = Dense(256, activation='relu')(decoder1)
    outputs = Dense(1652, activation='softmax')(decoder2)
    model = Model(inputs=[inputs1, inputs2], outputs=outputs)

    model.layers[2].set_weights([embedding_matrix])
    model.layers[2].trainable = False
    model.load_weights('./model_9.h5')
    images = 'C:/Users/rode/Desktop/Projects/IC_app/Flickr8k_Dataset/Flicker8k_Dataset/'
    with open("C:/Users/rode/Desktop/Projects/IC_app/encoded_.pkl", "rb") as encoded_pickle:
        encoding_test = load(encoded_pickle)


    z=0
    pic = list(encoding_test.keys())[z]
    image = encoding_test[pic].reshape((1,2048))
    x=plt.imread(images+pic)
    # plt.imshow(x)
    # plt.show()
    final=greedySearch(image)
    return render_template('predict.html', f=final)












if __name__=="__main__":
    app.run(debug=False, threaded=False)
