#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Tuple, List
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
import os
import random
import tensorflow as tf
from keras import backend as K
from keras.models import Sequential
from keras.layers import Dense, InputLayer
from keras.utils import print_summary
import json


# In[ ]:


tf.logging.set_verbosity(tf.logging.ERROR)


# In[ ]:


def set_seed(seed:int):
    """Set the random state of the various random extractions.
        seed:int, the seed to set the random state to.
    """
    np.random.seed(seed)
    random.seed(seed)
    tf.set_random_seed(seed)


# In[ ]:


def is_gpu_available():
    return bool(K.tensorflow_backend._get_available_gpus())


# In[ ]:


def isnotebook():
    try:
        shell = get_ipython().__class__.__name__
        if shell == 'ZMQInteractiveShell':
            return True   # Jupyter notebook or qtconsole
        elif shell == 'TerminalInteractiveShell':
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except NameError:
        return False      # Probably standard Python interpreter


# In[ ]:


if isnotebook():
    from tqdm import tqdm_notebook as tqdm
    from keras_tqdm import TQDMNotebookCallback as ktqdm
else: 
    from tqdm import tqdm
    from keras_tqdm import TQDMCallback as ktqdm


# In[ ]:


def load_dataset(x:str, y:str)->Tuple[np.ndarray, np.ndarray]:
    return pd.read_csv(x, index_col=0).values, pd.read_csv(y, index_col=0).values


# In[ ]:


def scale(train:np.ndarray, test:np.ndarray):
    """Return scaler, scaled training and test vectors based on given training vector."""
    scaler = MinMaxScaler().fit(train)
    return scaler.transform(train), scaler.transform(test)


# In[ ]:


def split_dataset(dataset:Tuple[np.ndarray, np.ndarray], seed:int, test_size:float=0.3)->Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return the given dataset split among training a test set for the given random seed.
        dataset:Tuple[np.ndarray, np.ndarray], the dataset to split.
        seed:int, the seed to use for the random split.
    """
    return train_test_split(*dataset, test_size=test_size, random_state=seed)


# In[ ]:


def scale_split_dataset(dataset, seed:int, test_size:float=0.3):
    """Return split and scaled dataset."""
    x_train, x_test, y_train, y_test = split_dataset(dataset, seed, test_size)
    return (*scale(x_train, x_test), y_train, y_test)


# In[ ]:


def auprc(y_true, y_pred)->float:
    score = tf.metrics.auc(y_true, y_pred, curve="PR", summation_method="careful_interpolation")[1]
    K.get_session().run(tf.local_variables_initializer())
    return score


# In[ ]:


def mlp(input_size:int):
    """Return a multi-layer perceptron."""
    set_seed(42)
    model = Sequential([
        InputLayer(input_shape=(input_size,)),
        *[Dense(input_size, activation="relu") for i in range(5)],
        Dense(1, activation="sigmoid")
    ])
    model.compile(
        optimizer="nadam",
        loss='mean_squared_error',
        metrics=[auprc]
    )
    return model


# In[ ]:


def fit(model:Sequential, x_train:np.ndarray, x_test:np.ndarray, y_train:np.ndarray, y_test:np.ndarray, epochs:int, batch_size:int):
    """Train the given model on given train data for the given epochs number.
        model:Sequential, the model to be trained.
        x_train:np.ndarray, the input for training the model.
        x_test:np.ndarray, the input for testing the model.
        y_train:np.ndarray, the output labels for training the model.
        y_test:np.ndarray, the output labels for testing the model.
        epochs:int, number of epochs for which to train the model.
        initial_epoch:int, starting epoch.
        batch_size:int, number of datapoints per training batch.
    """
    return model.fit(
        x_train,
        y_train,
        shuffle=True,
        verbose=0,
        validation_data=(x_test, y_test),
        epochs=epochs,
        callbacks=[ktqdm()],
        batch_size=batch_size
    )


# In[ ]:


def store_auprc(batch_size:int, holdout:int, auprc:float, path:str="auprcs.json"):
    if os.path.exists("auprcs.json"):
        with open("auprcs.json", "r") as f:
            auprcs = json.load(f)
    else:
        auprcs = {}
    if batch_size not in auprcs:
        auprcs[batch_size] = {}
    if holdout not in auprcs[batch_size]:
        auprcs[batch_size][holdout] = auprc
    with open("auprcs.json", "w") as f:
        json.dump(auprcs, f)


# In[ ]:


def is_auprc_cached(batch_size:int, holdout:int, path:str="auprcs.json"):
    with open("auprcs.json", "r") as f:
        auprcs = json.load(f)
        return batch_size in auprcs and holdout in auprcs[batch_size]


# In[ ]:


def train_holdouts(batch_size:int, holdouts:int, dataset, epochs:int):
    [
        store_auprc(
            batch_size,
            holdout,
            fit(
                mlp(26),
                *scale_split_dataset(dataset, holdout),
                epochs, 
                batch_size
            ).history["val_auprc"][-1])
        for holdout in tqdm(range(holdouts), desc="Holdouts for batch_size {batch_size}".format(batch_size=batch_size), leave=False)
        if not is_auprc_cached(batch_size, holdout)
    ]


# In[ ]:


def train_batch_sizes(batch_sizes:List[int], datapoints:str, labels:str, holdouts:int, epochs:int):
    dataset = load_dataset(datapoints, labels)
    [
        train_holdouts(batch_size, holdouts, dataset, epochs) 
        for batch_size in tqdm(batch_sizes, desc="Batch sizes")
    ]


# In[ ]:


def get_batch_sizes(n:int, offset:int=2):
    return [
        i**2 + int(1.175**i) for i in range(offset, n+offset)
    ]


# In[ ]:


holdouts = 10
epochs = 100
batch_sizes = get_batch_sizes(50)
if is_gpu_available():
    print("Working with GPU!")
train_batch_sizes(batch_sizes, "folds/x_4.csv", "folds/y_4.csv", holdouts, epochs)

