import torch
from tqdm import tqdm

from config import TrainingConfig, BiLSTMConfig
from models.BiLSTM import BiLSTM, cal_loss
from utils.utils import expand_vocabulary
from evaluating import Metrics


class BiLSTM_opration:

    def __init__(self, train_data, dev_data, test_data, word2id, tag2id):
        self.train_word_lists, self.train_tag_lists = train_data
        self.dev_word_lists, self.dev_tag_lists = dev_data
        self.test_word_lists, self.test_tag_lists = test_data
        self.word2id, self.tag2id = expand_vocabulary(word2id, tag2id)
        self.id2tag = dict((id, tag) for tag, id in tag2id.items())
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        # self.device = 'cpu'

        self.model = BiLSTM(
            vocab_size=len(self.word2id),
            tagset_size=len(self.tag2id),
            embedding_dim=BiLSTMConfig.input_size,
            hidden_dim=BiLSTMConfig.hidden_size
        ).to(self.device)
        self.optimizer = torch.optim.Adam(params=self.model.parameters(), lr=TrainingConfig.lr)


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
            sentence = word_lists[0]
            wordID_lists = torch.LongTensor(size=(1, len(sentence))).to(self.device)
            for i, word in enumerate(sentence):
                wordID_lists[0][i] = self.word2id.get(word, self.word2id['<unk>'])
            return wordID_lists
        else:
            # 用于 train、validate、evaluate函数
            # print(word_lists)
            wordID_lists = (torch.ones(size=(len(word_lists), len(word_lists[0])), dtype=torch.long) * self.word2id['<pad>']).to(self.device)
            tagID_lists = (torch.ones(size=(len(word_lists), len(word_lists[0])), dtype=torch.long) * self.tag2id['<pad>']).to(self.device)
            for i in range(len(word_lists)):
                for j in range(len(word_lists[i])):
                    wordID_lists[i][j] = self.word2id.get(word_lists[i][j], self.word2id['<unk>'])      # 遇到词表中不存在的字符，使用<unk>代替
                    tagID_lists[i][j] = self.tag2id[tag_lists[i][j]]
            return wordID_lists, tagID_lists

    def _predtion_to_tags(self, prediction):
        """将模型给出的预测结果转化为标签序列"""
        return [self.id2tag[id.item()] for id in torch.argmax(prediction, dim=2)[0]]


    def train(self):
        """训练
        数据以batch的形式输入模型, 同一个batch中的序列使
        用<pad>填补至与该batch中最长序列相同的长度, 故每
        个batch的序列长度为不同"""
        # 根据sentence的长度 重排train_data
        # 此举可以减少同一个batch中的每个sentence之间
        # 的长度差距，这意味只需添加最少数量的 <pad>
        train_word_lists, train_tag_lists = self._sort_by_sentence_lengths(self.train_word_lists, self.train_tag_lists)

        epochs = TrainingConfig.epochs
        batch_size = TrainingConfig.batch_size
        iteration_size = round(len(train_word_lists) / batch_size + 0.49)

        for epoch in range(epochs):
            losses = 0.
            with tqdm(total=iteration_size, desc='Epoch %d/%d Training' %(epoch, epochs)) as pbar:
                # one batch
                for step in range(iteration_size):
                    # batch data
                    batch_sentences, batch_targets = self._tokenizer(
                        train_word_lists[batch_size * step: min(batch_size * (step+1), len(train_word_lists))],
                        train_tag_lists[batch_size * step: min(batch_size * (step+1), len(train_tag_lists))]
                    )
                    # forword
                    self.model.train()
                    self.model.zero_grad()
                    prediction = self.model.forward(batch_sentences)
                    # loss
                    loss = cal_loss(prediction, batch_targets, self.tag2id).to(self.device)
                    loss.backward()
                    self.optimizer.step()
                    losses += loss.item()
                    
                    if step % 10 == 0 and step != 0: pbar.set_postfix(ave_loss=losses/(step+1))
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
                prediction = self.model.forward(val_sentences)
                # loss
                loss = cal_loss(prediction, val_targets, self.tag2id).to(self.device)
                val_losses += loss.item()
            val_losses = val_losses / iteration_size

            return val_losses

    def evaluate(self, file_path):
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
                loss = cal_loss(prediction, tagID_list, self.tag2id)
                
                if i % 100 == 0: print(f'{i}/{len(self.test_word_lists)} : loss={loss}')
                pred_tag_lists.append(self._predtion_to_tags(prediction))
            # 计算评估值
            metrics = Metrics(file_path, self.test_tag_lists, pred_tag_lists)
            metrics.report_scores(dtype='BiLSTM')

    def predict(self, sentence):
        """预测
        : params sentence 单个文本"""
        sentence_token = self._tokenizer([sentence])
        torch.no_grad()
        prediction = self.model.forward(sentence_token)
        pred_tags = self._predtion_to_tags(prediction)
        return pred_tags, prediction



if __name__ == '__main__':
    
    from data import build_corpus
    
    train_word_lists, train_tag_lists, word2id, tag2id = build_corpus("train")
    dev_word_lists, dev_tag_lists = build_corpus("dev", make_vocab=False)
    test_word_lists, test_tag_lists = build_corpus("test", make_vocab=False)

    bilstm_opration = BiLSTM_opration(
        train_data=(train_word_lists, train_tag_lists),
        dev_data=(dev_word_lists, dev_tag_lists),
        test_data=(test_word_lists, test_tag_lists),
        word2id=word2id,
        tag2id=tag2id
    )

    bilstm_opration.train()
    bilstm_opration.evaluate(file_path='./zdata')