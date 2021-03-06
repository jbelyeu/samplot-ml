#!/usr/bin/env python3
import os
import sys
import pprint
import argparse
import functools
import numpy as np
import tensorflow as tf
from data_processing import datasets
from model_code import models, utils
import tensorflow_addons as tfa
import matplotlib.pyplot as plt

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

model_index = {
    'baseline': functools.partial(
        models.Baseline, 
        input_shape=datasets.IMAGE_SHAPE),
    'CNN' : models.CNN,
}


def get_compiled_model(model_type, model_params=None, compile_params=None):
    """
    Returns a compiled model with given model/compile parameters
    """
    if model_params:
        model = model_type(**model_params)
    else:
        model = model_type()

    model.compile(**compile_params)

    return model



# -----------------------------------------------------------------------------
# Subcommand functions
# -----------------------------------------------------------------------------
def predict(args):
    if args.use_h5:
        model = tf.keras.models.load_model(args.model_path)
    else:
        model = model_index[args.model_type]()
        model.load_weights(filepath=args.model_path).expect_partial()

    if args.image.endswith('.txt'): # list of images
        # with open(args.image, 'r') as file:
        #     for image in file:
        #         pred = utils.display_prediction(image.rstrip(), model,
        #                                         augmentation=args.augmentation)
        #         print(os.path.splitext(os.path.basename(image))[0], 
        #               *pred, sep='\t')
        dataset = datasets.DataWriter.get_basic_dataset(args.image, args.num_processes)
        dataset = dataset.batch(args.batch_size, drop_remainder=False) \
                         .prefetch(buffer_size=tf.data.experimental.AUTOTUNE)

        for filenames, images in dataset:
            predictions = model(images)
            for filename, prediction in zip(filenames, predictions):
                f = os.path.splitext(os.path.basename(filename.numpy()))[0]
                f = f.decode().split('_')
                print(*f[:3], sep='\t', end='\t')
                print(*prediction.numpy(), sep='\t')
    else:
        pred = utils.display_prediction(args.image, model,
                                        augmentation=args.augmentation)
        print(os.path.splitext(os.path.basename(args.image))[0], 
              *pred, sep='\t')

def evaluate(args):
    if args.use_h5:
        model = tf.keras.models.load_model(args.model_path)
    else:
        model = model_index[args.model_type]()
        model.load_weights(filepath=args.model_path).expect_partial()
    utils.evaluate_model(model, data_dir= args.data_dir, 
                         batch_size=args.batch_size)

def train(args):
    pprint.pprint(vars(args))

    # load data
    training_set, n_train = datasets.DataReader(
        augmentation=True,
        num_processes=args.processes,
        batch_size=args.batch_size,
        data_list=args.train_list,
        tfrec_list=args.train_tfrec_list).get_dataset()

    val_set, n_val = datasets.DataReader(
        augmentation=False,
        num_processes=args.processes,
        batch_size=args.batch_size,
        data_list=args.val_list,
        tfrec_list=args.val_tfrec_list).get_dataset()

    print(f"Train on {n_train} examples.  Validate on {n_val} examples.")

    # setup training
    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            filepath=args.save_to,
            monitor='val_loss',
            verbose=1,
            save_best_only=True),
    ]

    lr_schedule = tf.keras.experimental.CosineDecayRestarts(
        initial_learning_rate=args.lr,
        alpha=0.0001,
        t_mul=2.0,
        m_mul=1.25,
        first_decay_steps=np.ceil(n_train/(args.batch_size/4))) # ie. two epochs


    # TODO eventually I'd like to optionally be able to load these from a JSON
    model_params = {'num_classes': args.num_classes}
    loss = tf.keras.losses.CategoricalCrossentropy
    metrics=['CategoricalAccuracy']
    compile_params = dict(
        loss=loss(
            label_smoothing=args.label_smoothing,
        ),
        optimizer=#tfa.optimizers.Lookahead(
            tfa.optimizers.SGDW(
                weight_decay=args.weight_decay,
                learning_rate=lr_schedule,
                momentum=args.momentum,
                nesterov=True,
            ),
        #),
        metrics=metrics)
    model = get_compiled_model(
        model_index[args.model_type], 
        model_params, 
        compile_params)

    model.fit(
        training_set,
        steps_per_epoch=np.ceil(n_train/args.batch_size),
        validation_data=val_set,
        validation_steps=np.ceil(n_val/args.batch_size),
        epochs=args.epochs,
        callbacks=callbacks,
        verbose=args.verbose
    )


# -----------------------------------------------------------------------------
# Get arguments
# -----------------------------------------------------------------------------
parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(title='Subcommands')

# prediction subcommand -------------------------------------------------------
predict_parser = subparsers.add_parser(
    'predict', help='Use a trained model to classify an image.',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
predict_parser.add_argument(
    '--model-path', '-mp', dest='model_path', type=str, required=True,
    help='Path of trained model')
predict_parser.add_argument(
    '--model-type', '-mt', dest='model_type', type=str, required=False,
    choices=model_index.keys(), default='CNN', help='Type of model to load.')
predict_parser.add_argument(
    '--use-h5', '-h5', dest='use_h5', action='store_true')
predict_parser.add_argument(
    '--augmentation', '-a', dest='augmentation', action='store_true',
    help='Use test time augmentation.')
predict_parser.add_argument(
    '--image', '-i', dest='image', type=str, required=True,
    help='Path of image')
predict_parser.add_argument(
    '--num_processes', '-n', dest='num_processes', type=int, default=1,
    help='number of processes to use when loading images')
predict_parser.add_argument(
    '--batch_size', '-b', dest='batch_size', type=int, default=32)
predict_parser.set_defaults(
    func=predict)

# evaluation subcommand -------------------------------------------------------
eval_parser = subparsers.add_parser(
    'evaluate', help='Evaluate a trained model on a labelled dataset',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
eval_parser.add_argument(
    '--model-path', '-mp', dest='model_path', type=str, required=True,
    help="Path of trained model (before the dot '.')")
eval_parser.add_argument(
    '--model-type', '-mt', dest='model_type', type=str, required=False,
    choices=model_index.keys(), default='CNN', help='Type of model to load.')
eval_parser.add_argument(
    '--use-h5', '-h5', dest='use_h5', action='store_true')
eval_parser.add_argument(
    '--data-dir', '-d', dest='data_dir', type=str, required=True,
    help='Root data directory for test set.')
eval_parser.add_argument(
    '--batch-size', '-b', dest='batch_size', type=int, required=False,
    default=80, help='Number of images to feed to model at a time.')
eval_parser.set_defaults(
    func=evaluate)

# training subcommand ---------------------------------------------------------
train_parser = subparsers.add_parser(
    'train', help='Train a new model.',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
train_parser.add_argument(
    '--verbose', '-v', dest='verbose', type=int, default=1,
    help='verbosity level passed to keras fit function.')
train_parser.add_argument(
    '--processes', '-p', dest='processes', type=int, default=1,
    help='Number of processes used in fetching data.')
train_parser.add_argument(
    '--batch-size', '-b', dest='batch_size', type=int, required=False,
    default=80, help='Number of images to feed to model at a time.')
train_parser.add_argument(
    '--epochs', '-e', dest='epochs', type=int, required=False,
    default=100, help='Max number of epochs to train model.')
train_parser.add_argument(
    '--model-type', '-mt', dest='model_type', type=str, required=False,
    default='CNN', help='Type of model to train.')
train_parser.add_argument(
    '--num-classes', '-n', dest='num_classes', type=int, required=False,
    default='3', help='Number of possible class labels')
train_parser.add_argument(
    '--train-list', dest='train_list', type=str, required=True,
    help='File containing list of images in train set.')
train_parser.add_argument(
    '--val-list', dest='val_list', type=str, required=True,
    help='File containing list of images in val set.')
train_parser.add_argument(
    '--train-tfrec-list', dest='train_tfrec_list', type=str, required=True,
    help='File containing list of train tfrecord paths (s3 or local).')
train_parser.add_argument(
    '--val-tfrec-list', dest='val_tfrec_list', type=str, required=True,
    help='File containing list of val tfrecord paths (s3 or local).')
train_parser.add_argument(
    '--learning-rate', '-lr', dest='lr', type=float, required=False,
    default=1e-4, help='Learning rate for optimizer.')
train_parser.add_argument(
    '--momentum', '-mom', dest='momentum', type=float, required=False,
    default=0.9, help='Momentum term in SGD optimizer.')
train_parser.add_argument(
    '--weight-decay', '-w', dest='weight_decay', type=float, required=False,
    default=0, help='Weight decay strength')
train_parser.add_argument(
    '--label-smoothing', '-ls', dest='label_smoothing', type=float, required=False,
    default=0.0, help='Strength of label smoothing (0-1).')
train_parser.add_argument(
    '--save-to', '-s', dest='save_to', type=str, required=False,
    default=None, help='filename if you want to save your trained model.')
train_parser.set_defaults(
    func=train)

args = parser.parse_args()

if len(sys.argv) == 1:
    parser.print_help()
    parser.exit()

args.func(args)
