import os
import torch
from tqdm import tqdm
from transformers import BertTokenizer

from config import BiLSTMCRFTrainConfig, BiLSTMConfig
from models.BERT_BiLSTM_CRF import BiLSTM_CRF
from utils.utils import expand_vocabulary
from evaluating import Metrics
from data import token_to_str

# torch.cuda.set_device(3, 4)


os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "4,7"
device_ids = [0, 1]



class BiLSTM_opration:

    def __init__(self, train_data, dev_data, test_data, word2id, tag2id):
        self.train_word_lists, self.train_tag_lists = train_data
        self.dev_word_lists, self.dev_tag_lists = dev_data
        self.test_word_lists, self.test_tag_lists = test_data
        self.word2id, self.tag2id = expand_vocabulary(word2id, tag2id, crf=True, bert=True)
        self.id2tag = dict((id, tag) for tag, id in tag2id.items())
        self.tokenizer = BertTokenizer.from_pretrained('bert-base-chinese')

        self.device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
        # self.device = torch.device('cuda')

        model = BiLSTM_CRF(
                vocab_size=len(self.word2id),
                tagset_size=len(self.tag2id),
                config=BiLSTMConfig,
                tag2id=tag2id
        )
        self.model = torch.nn.DataParallel(
            module=model,
            device_ids=device_ids
        )
        self.model.to(self.device)
        self.optimizer = torch.nn.DataParallel(
            torch.optim.Adam(params=self.model.parameters(), lr=BiLSTMCRFTrainConfig.lr),
            device_ids=device_ids
        )
        # self.optimizer = torch.optim.Adam(params=self.model.parameters(), lr=BiLSTMCRFTrainConfig.lr)



    def _sort_by_sentence_lengths(self, word_lists, tag_lists):
        """将 word_lists和tag_lists 根据sentence序列的长度
        降序排序, 此举可以有效保证每个batch中的sentence序列
        长度相近, 减少< pad> 占位符的用量
        """
        pairs = list(zip(word_lists, tag_lists))
        indices = sorted(range(len(pairs)), key=lambda x:len(pairs[x][0]), reverse=True)
        
        pairs = [pairs[i] for i in indices]
        word_lists, tag_lists = list(zip(*pairs))

        return word_lists, tag_lists

    def _tokenizer(self, word_lists, tag_lists=None):
        """将 word和tag 转换为 词表(word2id)和标签表(tag2id)中对应的id
        :params word_lists    文本（以单个汉字为单位）序列    类型: python.List
        :params tag_lists     标签序列                      类型: python.List
        :return wordID_lists  文本id序列                    类型: pytorch.LongTensor
        :return tagID_lists   标签id序列                    类型: pytorch.LongTensor
        """

        if tag_lists is None:
            # 用于 predict函数
            assert len(word_lists == 1)
            # sentence = word_lists[0]
            # wordID_lists = torch.LongTensor(size=(1, len(sentence))).to(self.device)
            # for i, word in enumerate(sentence):
            #     wordID_lists[0][i] = self.word2id.get(word, self.word2id['<unk>'])
            # return wordID_lists

            sentence = token_to_str(word_lists)[0]

            token = self.tokenizer(
                text=sentence,
                padding='max_length',
                max_length=max_len+2,
                return_tensors='pt'
            )['input_ids'].to(self.device)
            return token


        else:
            # 用于 train、validate、evaluate函数

            max_len = len(word_lists[0])
            # print('max_len:', max_len)
            
            sentences = token_to_str(word_lists)
            # print(sentences)
            token = self.tokenizer(
                text=sentences,
                padding='max_length',
                max_length=max_len+2 if (max_len+2) < 512 else 512,
                truncation=True,
                return_tensors='pt'
            )['input_ids'].to(self.device)
            # print(token.device)


            if len(tag_lists[0]) > 512: seq_len = 512
            else: seq_len = len(tag_lists[0])

            tagID_lists = (torch.ones(size=(len(tag_lists), seq_len), dtype=torch.long) * self.tag2id['<pad>']).to(self.device)
            for i in range(len(tag_lists)):

                if len(tag_lists[i]) > 512: seq_len = 512
                else: seq_len = len(tag_lists[i])

                for j in range(seq_len):
                    # wordID_lists[i][j] = self.word2id.get(word_lists[i][j], self.word2id['<unk>'])      # 遇到词表中不存在的字符，使用<unk>代替
                    tagID_lists[i][j] = self.tag2id[tag_lists[i][j]]
                # wordID_lists[i][-1] = self.word2id.get(word_lists[i][-1], self.word2id['<unk>'])
            # print(tagID_lists.device)

            return token, tagID_lists

    def _predtion_to_tags(self, prediction):
        """将模型给出的预测结果转化为标签序列"""
        # return [self.id2tag[id.item()] for id in torch.argmax(prediction, dim=2)[0]]
        return [self.id2tag.get(id) for id in prediction]


    def train(self):
        """训练
        数据以batch的形式输入模型, 同一个batch中的序列使
        用<pad>填补至与该batch中最长序列相同的长度, 故每
        个batch的序列长度为不同"""
        # 根据sentence的长度 重排train_data
        # 此举可以减少同一个batch中的每个sentence之间
        # 的长度差距，这意味只需添加最少数量的 <pad>
        train_word_lists, train_tag_lists = self._sort_by_sentence_lengths(self.train_word_lists, self.train_tag_lists)

        epochs = BiLSTMCRFTrainConfig.epochs
        batch_size = BiLSTMCRFTrainConfig.batch_size
        iteration_size = round(len(train_word_lists) / batch_size + 0.49)

        for epoch in range(epochs):
        # for epoch in range(5):
            losses = 0.
            with tqdm(total=iteration_size, desc='Epoch %d/%d Training' %(epoch, epochs)) as pbar:
                # one batch
                for step in range(iteration_size):
                    # batch data
                    batch_sentences, batch_targets = self._tokenizer(
                        train_word_lists[batch_size * step: min(batch_size * (step+1), len(train_word_lists))],
                        train_tag_lists[batch_size * step: min(batch_size * (step+1), len(train_tag_lists))]
                    )
                #     # forword
                    self.model.train()
                    self.model.zero_grad()
                    # prediction = self.model.module.forward(batch_sentences)
                    prediction = self.model(batch_sentences)

                    # loss
                    loss = self.model.module.neg_log_likelihood(prediction, batch_targets).to(self.device)
                    loss.backward()
                    self.optimizer.module.step()
                    losses += loss.item()
                    
                    if step % 2 == 0 and step != 0: pbar.set_postfix(ave_loss=losses/(step+1))
                    pbar.update(1)

                # 每个epoch结束后，使用验证集测试
                val_loss = self.validate(batch_size)
                pbar.set_postfix(ave_loss='{0:.3f}'.format(losses/iteration_size), val_loss='{0:.3f}'.format(val_loss))
            

    def validate(self, batch_size):
        """验证
        数据以batch的形式输入模型, 同一个batch中的序列使
        用<pad>填补至与该batch中最长序列相同的长度, 故每
        个batch的序列长度为不同"""
        dev_word_lists, dev_tag_lists = self._sort_by_sentence_lengths(self.dev_word_lists, self.dev_tag_lists)

        # print(dev_word_lists)

        self.model.eval()
        with torch.no_grad():
            val_losses = 0
            iteration_size = round(len(self.dev_word_lists) / batch_size + 0.5)
            for step in range(iteration_size):
                # validate batch data

                val_sentences, val_targets = self._tokenizer(
                    dev_word_lists[batch_size * step: min(batch_size * (step+1), len(dev_word_lists))],
                    dev_tag_lists[batch_size * step: min(batch_size * (step+1), len(dev_tag_lists))]
                )
                # forward
                # prediction = self.model.module.forward(val_sentences)
                prediction = self.model(val_sentences)
                # loss
                loss = self.model.module.neg_log_likelihood(prediction, val_targets).to(self.device)
                val_losses += loss.item()
            val_losses = val_losses / iteration_size

            return val_losses

    def evaluate(self, file_path: str):
        """评估
        一个batch只有一条序列, 无需<pad>"""
        self.model.eval()
        with torch.no_grad():
            pred_tag_lists = []
            for i, (word_list, tag_list) in enumerate(zip(self.test_word_lists, self.test_tag_lists)):
                # test data
                wordID_list, tagID_list = self._tokenizer([word_list], [tag_list])
                # forward
                prediction = self.model.forward(wordID_list)
                # loss
                # loss = cal_bilstm_crf_loss(prediction, tagID_list, self.tag2id)
                
                # if i % 100 == 0: print(f'{i}/{len(self.test_word_lists)} : loss={loss}')

                # print(prediction.shape)

                # best_path = self.model.test(prediction, [prediction.shape[1]], self.tag2id)
                best_path = self.model.module.vibiter_decoding(prediction[0])
                pred_tag_lists.append(
                    self._predtion_to_tags(
                        best_path
                    )
                )

                
                print(word_list)
                print(tag_list)
                print(self._predtion_to_tags(
                        best_path
                    ))

            # 计算评估值
            metrics = Metrics(file_path, self.test_tag_lists, pred_tag_lists)
            metrics.report_scores(dtype='BiLSTM-CRF')

    def predict(self, sentence):
        """预测
        : params sentence 单个文本"""
        sentence_token = self._tokenizer([sentence])
        torch.no_grad()
        prediction = self.model.forward(sentence_token)
        pred_tags = self._predtion_to_tags(prediction)
        return pred_tags, prediction



if __name__ == '__main__':
    
    from data import build_corpus, token_to_str
    from utils.utils import expand_4_bert
    
    train_word_lists, train_tag_lists, word2id, tag2id = build_corpus("train", data_dir='./data/')
    dev_word_lists, dev_tag_lists = build_corpus("dev", make_vocab=False, data_dir='./data/')
    test_word_lists, test_tag_lists = build_corpus("test", make_vocab=False, data_dir='./data/')

    # tag2id['<cls>'] = len(tag2id)
    # tag2id['<seq>'] = len(tag2id)

    train_tag_lists = expand_4_bert(train_tag_lists)
    dev_tag_lists = expand_4_bert(dev_tag_lists)
    test_tag_lists = expand_4_bert(test_tag_lists)


    # print(test_word_lists)

    # train_sentence_list = token_to_str(train_word_lists)
    # dev_sentence_list = token_to_str(dev_word_lists)
    # test_sentence_list = token_to_str(test_word_lists)

    # print(train_sentence_list)

    bilstm_opration = BiLSTM_opration(
        train_data=(train_word_lists, train_tag_lists),
        dev_data=(dev_word_lists, dev_tag_lists),
        test_data=(test_word_lists, test_tag_lists),
        word2id=word2id,
        tag2id=tag2id
    )

    bilstm_opration.train()
    bilstm_opration.evaluate(file_path='./zdata')