import numpy as np

# Работа с датафреймом
import pandas as pd


# Обработка данных
import re, string
import emoji
import nltk
from sklearn import preprocessing
from imblearn.over_sampling import RandomOverSampler
from sklearn.model_selection import train_test_split


# Результаты BERT и roBert мы сравним с наивным байесовским классификатором
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.naive_bayes import MultinomialNB

# Токены и модели из библиотеки transformers
from transformers import BertTokenizerFast
from transformers import TFBertModel
from transformers import RobertaTokenizerFast
from transformers import TFRobertaModel

# Keras
import tensorflow as tf
from tensorflow import keras

# Метрики
from sklearn.metrics import accuracy_score, f1_score
from sklearn.metrics import classification_report, confusion_matrix

# Для воспроизводимости результатов
seed=42

# Настройка стилей для графиков
import matplotlib.pyplot as plt
import seaborn as sns
sns.set_style("whitegrid")
sns.despine()
plt.style.use("seaborn-whitegrid")
plt.rc("figure", autolayout=True)
plt.rc("axes", labelweight="bold", labelsize="large", titleweight="bold", titlepad=10)

# Отключим мешаюшие предупреждения
import warnings
warnings.filterwarnings("ignore")

        # или в более новых версиях
        df = pd.read_csv('/content/reviews.csv', encoding='utf-8', on_bad_lines='skip')
        
        df.head()
        
        #df = df.drop(columns=['Restaurant', 'Reviewer', 'Metadata', 'Time', 'Pictures', '7514'])
        
        df.drop_duplicates(inplace = True)
        
        df.shape
        
        df.isna().sum()
        
        df = df.dropna()
        
        df.info()
        
        df.shape
        
        df = df.iloc[:40000]

"""Импортируем библиотеки:

# Вспомогательные функции

Определим функцию для вывода матрицы ошибок.
"""

def conf_matrix(y, y_pred, title):
    fig, ax =plt.subplots(figsize=(5,5))
    labels = ['1', '2', '3', '4', '5']
    ax=sns.heatmap(confusion_matrix(y, y_pred), annot=True, cmap="Blues", fmt='g', cbar=False, annot_kws={"size":25})
    plt.title(title, fontsize=20)
    ax.xaxis.set_ticklabels(labels, fontsize=17)
    ax.yaxis.set_ticklabels(labels, fontsize=17)
    ax.set_ylabel('Тест', fontsize=20)
    ax.set_xlabel('Предсказание', fontsize=20)
    plt.show()

"""### Предобработка и анализ данных"""

df.rename(columns={'Review': 'OriginalTweet', 'Rating': 'Sentiment'}, inplace=True)

"""Определим функцию очистки"""

# Очистка emojis из текстов
def strip_emoji(text):
    return re.sub(emoji.get_emoji_regexp(), r"", text)  # удаляем emoji (смайлики)

# Удаляем пунктуацию, ссылки, упоминание других участников, символы конца строки и переноса \r\n
def strip_all_entities(text):
    text = text.replace('\r', '').replace('\n', ' ').lower()  # удаляем \n и \r и переводим строку в нижний регистр
    text = re.sub(r"(?:\@|https?\://)\S+", "", text)  # удаление ссылок и упоминаний других участников
    text = re.sub(r'[^\x00-\x7fА-Яа-яЁё]', r'', text)  # удаление символов не utf8/ascii, оставляя кириллицу
    banned_list = string.punctuation + '…' + '«' + '»' + '—'  # добавление специфичных для русского символов
    table = str.maketrans('', '', banned_list)  # создание словаря замены
    text = text.translate(table)  # применение к строке словаря замены
    return text

# Убираем хэштеги в конце предложения и оставляем в середине, удалив только символ #
def clean_hashtags(tweet):
    new_tweet = " ".join(word.strip() for word in re.split('#(?!(?:hashtag)\b)[\wа-яА-ЯёЁ-]+(?=(?:\s+#[\wа-яА-ЯёЁ-]+)*\s*$)', tweet))  # удаление последнего хэштега
    new_tweet2 = " ".join(word.strip() for word in re.split('#|_', new_tweet))  # удаление символа хэштега в середине предложения
    return new_tweet2

# Фильтрация специальных символов, таких как & и $, присутствующих в некоторых словах
def filter_chars(a):
    sent = []
    for word in a.split(' '):
        if ('&' in word):  # Убираем слова, содержащие '&'
            sent.append('')
        else:
            sent.append(word)
    return ' '.join(sent)

def remove_mult_spaces(text):  # удаление множественных пробелов с помощью регулярки
    return re.sub("\s\s+", " ", text)

"""Применим функции для очистки"""

texts_new = []
for t in df.OriginalTweet:
    texts_new.append(remove_mult_spaces(filter_chars(clean_hashtags(strip_all_entities(strip_emoji(t))))))

"""Теперь мы можем создать новую колонку `text_clean` для размещения очищенной версии текста твитов."""

df['text_clean'] = texts_new

df['text_clean'].head()

df['OriginalTweet'][1:4].values

df['text_clean'][1:4].values

"""Также давайте создадим столбец для оценки длины очищенного текста, чтобы контролировать, а не удалили ли мы весь твит?"""

text_len = []
for text in df.text_clean:
    tweet_len = len(text.split())
    text_len.append(tweet_len)

df['text_len'] = text_len

plt.figure(figsize=(7,5))
ax = sns.countplot(x='text_len', data=df[df['text_len']<10], palette='mako')
plt.title('Твиты с длиной сообщений менее 10 слов (обучающая выборка)')
plt.yticks([])
ax.bar_label(ax.containers[0])
plt.ylabel('Число таких твитов')
plt.xlabel('')
plt.show()

print(f"Форма обучающей выборки: {df.shape}")

df = df[df['text_len'] > 4] # удаляем из обучающей выборки твиты короче 4 слов

print(f"Форма обучающей выборки после очистки: {df.shape}")

"""### Токенизация

Будем использовать предобученный BERT-токенизатор.
"""

tokenizer = BertTokenizerFast.from_pretrained("kazars24/rubert-ner-drugname")

"""Применим токенизатор к "очищенным" данным:"""

token_lens = []

for txt in df['text_clean'].values:
    tokens = tokenizer.encode(txt, max_length=512, truncation=True)
    token_lens.append(len(tokens))

max_len=np.max(token_lens)

print(f"Максимальная длина токенизированной последовательности: {max_len}")

token_lens = []

for i,txt in enumerate(df['text_clean'].values):
    tokens = tokenizer.encode(txt, max_length=512, truncation=True)
    token_lens.append(len(tokens))

"""


Эти последовательности не на английском языке и должны быть удалены.
Отсортируем по убыванию числа токенов предложения:"""

df['token_lens'] = token_lens

df = df.sort_values(by='text_len', ascending=False)
df.head()

filtered_df = df.loc[df['token_lens'] < 100]

filtered_df.shape

df = filtered_df

df.info()

#df = df.iloc[16:]

df.shape

"""Теперь набор данных выглядит более чистым. Мы перетасуем его и сбросим индекс."""

df = df.sample(frac=1).reset_index(drop=True)

"""### Анализ колонки Sentiment (Настроение)"""

df['Sentiment'].value_counts()

#df.drop(df[df['Sentiment'] == 7].index, inplace=True)
#df.drop(df[df['Sentiment'] == 9].index, inplace=True)
#df.drop(df[df['Sentiment'] == 0].index, inplace=True)

"""### Балансировка классов

С помощью метода `RandomOverSampler`, мы увеличим выборки для классов с меньшим числом образцов. Это можно сделать различными способами, например, путем дублирования существующих примеров, генерации синтетических данных или комбинирования этих методов.
"""

# Создание экземпляра RandomOverSampler
ros = RandomOverSampler()

# Применение увеличения выборки к данным (X_resampled, y_resampled = ros.fit_resample(X, y))
train_x, train_y = ros.fit_resample(np.array(df['text_clean']).reshape(-1, 1), np.array(df['Sentiment']).reshape(-1, 1));

# Снова объединим выборки в DataFrame
train_os = pd.DataFrame(list(zip([x[0] for x in train_x], train_y)), columns = ['text_clean', 'Sentiment']);

"""В этом примере мы используем библиотеку `imbalanced-learn` для увеличения выборки с помощью `RandomOverSampler`. Этот метод случайным образом выбирает примеры из класса c меньшим числом примеров и дублирует их, пока не будет достигнут баланс."""

train_os['Sentiment'].value_counts()

"""Теперь классы сбалансированы.

### Обучающая, проверочная и тестовая выборки
"""

X = train_os['text_clean'].values
y = train_os['Sentiment'].values

X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.2, random_state=42)

X_valid, X_test, y_valid, y_test = train_test_split(X_temp, y_temp, test_size=0.5, random_state=42)

"""### One hot encoding

Также сделаем копии наших выборок, они нам еще пригодятся:
"""

y_train_le = y_train.copy()
y_valid_le = y_valid.copy()
y_test_le = y_test.copy()

ohe = preprocessing.OneHotEncoder() # создаем экземпляр класса OneHotEncoder()

# Формируем кодированные OHE метки для тренировочной, проверочной и тестовой выборок
y_train = ohe.fit_transform(np.array(y_train).reshape(-1, 1)).toarray()
y_valid = ohe.fit_transform(np.array(y_valid).reshape(-1, 1)).toarray()
y_test = ohe.fit_transform(np.array(y_test).reshape(-1, 1)).toarray()

print(f"Тренировочная выборка: {X_train.shape[0]}")
print(f"Проверочная выборка: {X_valid.shape[0]}")
print(f"Тестовая выборка: {X_test.shape[0]}")

"""### Базовая модель: Наивный байесовский классификатор

Токенизируем твиты, используя CountVectorizer:
"""

clf = CountVectorizer()
X_train_cv =  clf.fit_transform(X_train)
X_test_cv = clf.transform(X_test)

"""Преобразуем токенизированные твиты в формат TF-IDF (частота использования термина, умноженная на частоту использования документа):"""

tf_transformer = TfidfTransformer(use_idf=True).fit(X_train_cv)
X_train_tf = tf_transformer.transform(X_train_cv)
X_test_tf = tf_transformer.transform(X_test_cv)

"""Создаем модель наивного байесовского классификатора:"""

nb_clf = MultinomialNB()

"""Обучим его:"""

nb_clf.fit(X_train_tf, y_train_le)

"""Запустим предсказание на тестовой выборке:"""

nb_pred = nb_clf.predict(X_test_tf)

"""Выведем метрики с помощью метода `classification_report` библиотеки `sklearn`:"""

print('Расчет метрик для наивного байесовского классификатора:')
print()
print()
print(classification_report(y_test_le, nb_pred, target_names=['5', '4', '3', '2', '1']))

"""### Классификация с помощью BERT"""

def tokenize(data, max_len=128):
    input_ids = []
    attention_masks = []
    for i in range(len(data)):
        encoded = tokenizer.encode_plus(
            data[i],
            add_special_tokens=True,
            max_length=max_len,
            padding='max_length',  # Убедитесь, что последовательности имеют одинаковую длину
            truncation=True,       # Обрезаем длинные последовательности
            return_attention_mask=True
        )
        input_ids.append(encoded['input_ids'])
        attention_masks.append(encoded['attention_mask'])
 # Преобразуем списки в NumPy массивы
    return np.array(input_ids), np.array(attention_masks)

# Применяем функцию tokenize к выборкам
train_input_ids, train_attention_masks = tokenize(X_train)
val_input_ids, val_attention_masks = tokenize(X_valid)
test_input_ids, test_attention_masks = tokenize(X_test)

"""Применим функцию токенизатора к наборам данным и получим соответствующие маски:

Теперь мы можем импортировать предварительно обученную BERT модель из библиотеки Hugging face.
"""

bert_model = TFBertModel.from_pretrained("kazars24/rubert-ner-drugname") # префикс TF означает, что модель для TensorFlow

def create_model(bert_model, max_len=128):

    # Параметры обучения
    opt = tf.keras.optimizers.legacy.Adam(learning_rate=1e-5, decay=1e-7) # оптимизатор - Adam
    loss = tf.keras.losses.CategoricalCrossentropy()                      # функция потерь - категориальная кросс-энтропия
    accuracy = tf.keras.metrics.CategoricalAccuracy()                     # метрика - категориальная точность


    input_ids = tf.keras.Input(shape=(max_len,), dtype='int32')         # вход для токенизированной последовательности

    attention_masks = tf.keras.Input(shape=(max_len,), dtype='int32')   # маска

    embeddings = bert_model([input_ids, attention_masks])[1]            # BERT-модель

    output = tf.keras.layers.Dense(5, activation="softmax")(embeddings) # полносвязный слой для классификации OHE

    model = tf.keras.models.Model(inputs = [input_ids, attention_masks], outputs = output)

    model.compile(opt, loss=loss, metrics=accuracy)


    return model

model = create_model(bert_model)
model.summary()

"""Запускаем fine-tuning BERT трансформера:"""

history_bert = model.fit([train_input_ids, train_attention_masks], y_train, validation_data=([val_input_ids, val_attention_masks], y_valid), epochs=4, batch_size=16)

# Сохранение модели в формате TensorFlow SavedModel
model.save('my_model')

# Сохранение модели в формате HDF5
model.save('my_model.h5')

"""Запустим предсказание на тестовой выборке:"""

result_bert = model.predict([test_input_ids, test_attention_masks])

"""Возвращаем метку наиболее вероятного класса и строим матрицу ошибок:"""

y_pred_bert =  np.zeros_like(result_bert)
y_pred_bert[np.arange(len(y_pred_bert)), result_bert.argmax(1)] = 1

conf_matrix(y_test.argmax(1), y_pred_bert.argmax(1),'Матрица ошибок для BERT классификации')

print('Расчет метрик для BERT классификатора:')
print()
print()
print(classification_report(y_test, y_pred_bert, target_names=['5', '4', '3', '2', '1']))

for i in range(len(X_test[:10])):
    print(f'Text: {X_test[i]}')
    print(f'Predicted Class: {y_pred_bert[i]}')
    print(f'True Class: {y_test[i]}')
    print('-' * 50)
