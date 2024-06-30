import argparse
from minio import Minio

from data import build_corpus
from train_evaluate import hmm_train_eval, crf_train_eval, bilstm_train_eval, bilstm_crf_train_eval
from utils.preprocessing import Preprocessing
from utils.utils import save_model
from config import TrainingConfig, BiLSTMCRFTrainConfig

def parse_args():
    description = "你正在学习如何使用argparse模块进行命令行传参..."
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("-m", "--model", type=str, default='HMM', help="There are five models of NER, they are HMM, CRF, BiLSTM, BiLSTM_CRF and Bert_BiLSTM_CRF.")
    parser.add_argument("-p", "--path", type=str, default='./zdata/', help="data path")
    parser.add_argument('-on', '--filename', type=str, default='people_daily_BIO.txt', help='MinIO object name')
    parser.add_argument('-dr', '--datarate', type=list, default=[0.7, 0.1, 0.2], help='The rate of train_data, dev_data and test_data')
    parser.add_argument('-e', '--epochs', type=int, default=10, help='train epoch')
    parser.add_argument('-b', '--batch_size', type=int, default=16, help='batch size')
    parser.add_argument('-lr', '--learning_rate', type=float, default=0.0005, help='learning rate')
    parser.add_argument('-pp', "--pklpath", type=str, default='./model.pkl', help='the path and filename to save .pkl file')
    return parser.parse_args()
 
 
if __name__ == "__main__":
    args = parse_args()
    print(args)

    # preprocessing data
    data_preprocessing = Preprocessing(
        file_path=args.path,
        file_name=args.filename
    )
    data_preprocessing.train_test_dev_split(data_rate=args.datarate)
    data_preprocessing.construct_vocabulary_labels()
    
    # load data
    print('long data ...')
    train_word_lists, train_tag_lists, word2id, tag2id = build_corpus("train", data_dir=args.path)
    dev_word_lists, dev_tag_lists = build_corpus("dev", make_vocab=False, data_dir=args.path)
    test_word_lists, test_tag_lists = build_corpus("test", make_vocab=False, data_dir=args.path)

    if args.model == 'HMM':
        # train and evaluate HMM model
        model = hmm_train_eval(
            file_path=args.path,
            train_data=(train_word_lists, train_tag_lists),
            test_data=(test_word_lists, test_tag_lists),
            word2id=word2id,
            tag2id=tag2id
        )
    elif args.model == 'CRF':
        # train and evaluate CRF model
        model = crf_train_eval(
            file_path=args.path,
            train_data=(train_word_lists, train_tag_lists),
            test_data=(test_word_lists, test_tag_lists)
        )
    elif args.model == 'BiLSTM':
        # BiLSTM
        TrainingConfig.batch_size = args.batch_size
        TrainingConfig.epochs = args.epochs
        TrainingConfig.lr = args.learning_rate
        model = bilstm_train_eval(
            file_path=args.path,
            train_data=(train_word_lists, train_tag_lists),
            dev_data=(dev_word_lists, dev_tag_lists),
            test_data=(test_word_lists, test_tag_lists),
            word2id=word2id,
            tag2id=tag2id
        )
    elif args.model == 'BiLSTM_CRF':
        # BiLSTM CRF
        BiLSTMCRFTrainConfig.batch_size = args.batch_size
        BiLSTMCRFTrainConfig.epochs = args.epochs
        BiLSTMCRFTrainConfig.lr = args.learning_rate
        model = bilstm_crf_train_eval(
            file_path=args.path,
            train_data=(train_word_lists, train_tag_lists),
            dev_data=(dev_word_lists, dev_tag_lists),
            test_data=(test_word_lists, test_tag_lists),
            word2id=word2id,
            tag2id=tag2id
        )
    
    save_model(model, args.pklpath)