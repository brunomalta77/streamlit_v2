# building a stream lite application
import openai
import pandas as pd
import numpy as np
import re
import time
import string
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from dotenv import load_dotenv
import streamlit as st
import joblib
import glob
import os
import xlsxwriter
from io import BytesIO
from pyxlsb import open_workbook as open_xlsb
import requests
from PIL import Image
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import AgglomerativeClustering
from sklearn.cluster import DBSCAN
import numpy as np
import ast
import concurrent.futures




#Getting the API_Keys
#load_dotenv()
#api_key = os.getenv('API_Keys')

api_key = st.secrets["API_KEY"]
openai.api_key= api_key

#page config
st.set_page_config(page_title="BrandDelta_app",page_icon="💵",layout="wide")

logo_path = "brand_logo.png"
image = Image.open(logo_path)

col1, col2 = st.columns([4, 1])  # Adjust the width ratios as needed

# Logo on the left
with col2:
    st.image(image)  # Adjust the width as needed

# Title on the right
with col1:
    st.title("Brand Delta Topic Modelling (V 0.2)")
    st.subheader("Open AI version (0.28.1)")



@st.cache(allow_output_mutation=True,suppress_st_warning=True) 
def read_excel_parquet(df_file):
    if "parquet" in str(df_file):
        df = pd.read_parquet(df_file)
    if "xlsx" in str(df_file):
        df = pd.read_excel(df_file)
    uploaded_file_info= str(df_file)
    file_name = uploaded_file_info.split(", name='")[1].split(".")[0]
    df['Week Commencing'] = df['created_time'].apply(lambda x: (x - timedelta(days=x.weekday())).replace(hour=0, minute=0, second=0, microsecond=0))
    return df,uploaded_file_info,file_name



def my_values_filtered(df):
    author_options= [x for x in df["author_predictions"].unique()]
    author_options.append("All")
    channel_options= [x for x in df["message_type"].unique()]
    channel_options.append("All")
    br_options = [x for x in df["brand"].unique()]
    br_options.append("All")
    #time period
    start_date = st.date_input("Select start date")
    end_date =  st.date_input("Select end date")
    #convert our dates
    ws = start_date.strftime('%Y-%m-%d')
    we = end_date.strftime('%Y-%m-%d')
    # author
    res_author =  st.multiselect("Select the author categories:", author_options)
    res_channel = st.multiselect("Select the channel categories:", channel_options)
    res_br = st.multiselect("Select the brand that you want:", br_options)
    if "All" in res_channel:
        channel = [x for x in df["message_type"].unique()]
    else:
        channel = res_channel
        
    if "All" in res_author:
        author = [x for x in df["author_predictions"].unique()]
    else:
        author = res_author

    if "All" in res_br:
        brand = [x for x in df["brand"].unique()]
    else:
        brand = res_br
    return ws,we,author,channel,brand



# Remove topics with less than 5 words
def remove_noise_from_topics(topics):
    final_topic_list = []
    for top in topics:
        nw= top.split(" ")
        if len(nw) > 5:
            final_topic_list.append(top)
    return final_topic_list




def filtering(df,ws,we,author,channel,brand):
    df = df[(df['Week Commencing'] >= ws) & (df['Week Commencing'] <= we) & (df["author_predictions"].isin(author)) & (df["message_type"].isin(channel)) & (df["brand"].isin(brand))]
    df["cleaned_message"] = df["cleaned_message"].apply(lambda x: str(x))
    alldata = ' '.join(df["cleaned_message"])
    lengpt = len(alldata) / 4000   #(because chatgot maximum token size is 4076)
    posts_to_combine = round(len(df) / lengpt)
    df['nposts'] = np.arange(len(df))//posts_to_combine+1
    df['grouped_message'] = df.groupby(['nposts'])['cleaned_message'].transform(lambda x: ' '.join(x))
    return(df)

def my_values_all(df):
    author = [x for x in df["author_predictions"].unique()]
    channel = [x for x in df["message_type"].unique()]
    brand = [x for x in df["brand"].unique()]
    return author,channel,brand


def my_values_without_author(df,ws=None,we=None):
    channel_options= [x for x in df["message_type"].unique()]
    br_options = [x for x in df["brand"].unique()]
    if ws is None and we is None:
        return channel_options,br_options
    else:
        br_options.append("All")
        channel_options.append("All")
        start_date = st.date_input("Select start date")
        end_date =  st.date_input("Select end date")
        #convert our dates
        ws = start_date.strftime('%Y-%m-%d')
        we = end_date.strftime('%Y-%m-%d')
        
        res_channel = st.multiselect("Select the channel categories:", channel_options)
        res_br = st.multiselect("Select the brand categories:", br_options)
        if "All" in res_channel:
            channel = [x for x in df["message_type"].unique()]
        else:
            channel = res_channel

        if "All" in res_br:
            brand = [x for x in df["brand"].unique()]
        else:
            brand = res_br
        
        return ws,we,channel,brand



def filtering_all(df,author,channel,brand):
    df = df[(df["author_predictions"].isin(author)) & (df["message_type"].isin(channel)) & df["brand"].isin(brand)]
    df["cleaned_message"] = df["cleaned_message"].apply(lambda x: str(x))
    alldata = ' '.join(df["cleaned_message"])
    lengpt = len(alldata) / 4000   #(because chatgot maximum token size is 4076)
    posts_to_combine = round(len(df) / lengpt)
    df['nposts'] = np.arange(len(df))//posts_to_combine+1
    df['grouped_message'] = df.groupby(['nposts'])['cleaned_message'].transform(lambda x: ' '.join(x))
    return(df)


def filtering_without_author(df,channel,brand,ws=None,we=None):
    if ws is None and we is None:
        df = df[df["message_type"].isin(channel) & df["brand"].isin(brand)]
        df["cleaned_message"] = df["cleaned_message"].apply(lambda x: str(x))
        alldata = ' '.join(df["cleaned_message"])
        lengpt = len(alldata) / 4000   #(because chatgot maximum token size is 4076)
        posts_to_combine = round(len(df) / lengpt)
        df['nposts'] = np.arange(len(df))//posts_to_combine+1
        df['grouped_message'] = df.groupby(['nposts'])['cleaned_message'].transform(lambda x: ' '.join(x))
        return(df)
    else:
        df = df[(df['Week Commencing'] >= ws) & (df['Week Commencing'] <= we) & (df["message_type"].isin(channel)) & df["brand"].isin(brand)]
        df["cleaned_message"] = df["cleaned_message"].apply(lambda x: str(x))
        alldata = ' '.join(df["cleaned_message"])
        lengpt = len(alldata) / 4000   #(because chatgot maximum token size is 4076)
        posts_to_combine = round(len(df) / lengpt)
        df['nposts'] = np.arange(len(df))//posts_to_combine+1
        df['grouped_message'] = df.groupby(['nposts'])['cleaned_message'].transform(lambda x: ' '.join(x))
        return(df)



# generating the Chat GPT respose
@st.cache(allow_output_mutation=True,suppress_st_warning=True) 
def generate_chatgpt_response_v2(prompt, model = "gpt-3.5-turbo-16k"):
    time.sleep(5)
    responses = []
    restart_sequence = "\n"
    try:
        response = openai.ChatCompletion.create(
              model=model,
              messages=[{"role": "user", "content": prompt}],
              temperature=0,
              n=1, 
            request_timeout=5
            )
    
        return response['choices'][0]['message']['content']
        time.sleep(1)
    except Exception as e:
        # Handle the exception gracefully
        time.sleep(1)
        st.write(f"API call failed with error: {str(e)}")
        st.write("Continuing to the next iteration with a warning...")
        return('')
        


def generate_tags_get_topics(gm):
    try:
        prompt = "Act like a social media analyst tasked with finding the key topics or themes around food brands from a collection of social media posts.\
                                                 Determine exactly 2 topics that are being discussed \
                                                 in the text delimited by triple backticks. \
                                                 Make each topic 5 to 6 words long. \
                                                 If you find a similar theme or topic across multiple texts, please ensure that the topic name is exactly the same so they can be combined later. \
                                                 Please focus on larger themes and try not to make the topics very specific.\
                                                 Format your response as a list of items separated by commas \
                                                 Text: ```{}``` \
                                                 ".format(gm)
      
        return (generate_chatgpt_response_v2(prompt))
    except:
        return ('')


def get_topics(df):
    p = st.empty()
    progress_bar = st.progress(0)
    gr_msg_unique = list(df.grouped_message.unique())
    total_requests = len(gr_msg_unique)
    with st.spinner("Running...."):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            bar = st.progress(0)
            placeholder = st.empty()
            topics = list(executor.map(generate_tags_get_topics,(gm for gm in gr_msg_unique)))
            for idx,res in enumerate(topics,start=1):
                progress = idx/total_requests
                placeholder.text(f"{int(progress * 100)}%")
                # update progress bar
                bar.progress(progress)

        
    
    # Merging the topics with the actual dataframe
    topicdf = pd.DataFrame({'grouped_message': gr_msg_unique, 'topics': topics})
    df1 = pd.merge(df, topicdf, on='grouped_message', how='inner')
    return df1



#not being used
def get_topics_not_used(df):
    p = st.empty()
    progress_bar = st.progress(0)
    gr_msg_unique = list(df.grouped_message.unique())
    total_requests = len(gr_msg_unique)
    topics = []
    l=0
    for i,gm in  enumerate(gr_msg_unique):
        start_time = time.time()
        try:
            topics.append(generate_chatgpt_response_v2("Act like a social media analyst tasked with finding the key topics or themes around food brands from a collection of social media posts.\
                                                 Determine exactly 2 topics that are being discussed \
                                                 in the text delimited by triple backticks. \
                                                 Make each topic 5 to 6 words long. \
                                                 If you find a similar theme or topic across multiple texts, please ensure that the topic name is exactly the same so they can be combined later. \
                                                 Please focus on larger themes and try not to make the topics very specific.\
                                                 Format your response as a list of items separated by commas \
                                                 Text: ```{}``` \
                                                 ".format(gm)))
        except:
            topics.append('')
        print(l)
        l+=1

        
        if topics[l-1] == '':
            st.warning("Without any content")

        # Calculate progress
        progress_percentage = (i + 1) / total_requests * 100
        progress = (i + 1) / total_requests 
        progress_bar.progress(progress)
        
        end_time = time.time()
        elapsed_time = end_time - start_time

        # Print progress update
        p.text(f"Processing request {i + 1} of {total_requests} ({progress_percentage:.2f}% complete) time {round(elapsed_time,2)} S")
        
    
    # Merging the topics with the actual dataframe
    topicdf = pd.DataFrame({'grouped_message': gr_msg_unique, 'topics': topics})
    df1 = pd.merge(df, topicdf, on='grouped_message', how='inner')
    return df1



def unique_topics(df1):

    # create a list of all the unique topics 
    ind_topic_list=[]
    for topic in list(df1['topics'].unique()):
        ind_topic = topic.split('\n')
        ind_topic_list.append(ind_topic)
    flat_list = [item for sublist in ind_topic_list for item in sublist]

    final_topic_list=[]
    for item in flat_list:
        if item == '':
            continue
        elif '- ' in item:
            final_topic_list.append(item.split('- ')[1])
        elif '. ' in item:
            final_topic_list.append(item.split('. ')[1])

    # removing the topics with least than 5 letters 
    final_topic_list_cleaned = []
    for top in final_topic_list:
        nw = top.split(' ')
        if len(nw) > 5:
            final_topic_list_cleaned.append(top)
    
    return final_topic_list_cleaned


def best_10(final_topic_list_cleaned,df1,n=10):
    #giving the top 10 topics
    # we need to ask the client for how many topics they want.
    te = pd.DataFrame(final_topic_list_cleaned)
    te.rename(columns={0: 'topics'},inplace=True)
    te1 = pd.DataFrame(te.topics.value_counts()).reset_index()
    top_10_topics = list(te1[0:n]['topics'])
    cols_to_remove = [col for col in final_topic_list_cleaned if col not in top_10_topics]
    df2 = df1[df1.columns.difference(cols_to_remove)]
    # creating a binary column for the topics
    for top in top_10_topics:
        df2[top] = 0
    for top in top_10_topics:
        for index, row in df2.iterrows():
            rowtopics = row['topics']
            if top in rowtopics:
                df2.loc[index, top] = 1
            else:
                continue
    return top_10_topics,df2
    # saving the data frame.
    #df2.to_excel(r"C:\Users\Technology\Desktop\tasks\text_summary\IT_findus_nov-june.xlsx", index=False)



def Topics_num(final_topics,df,we,ws): #i am not using this, here because perphaps may be useful. 
    number_options = list(range(1,11))
    selected_number = st.selectbox("Num of topics",number_options)
    top_topics,final_df = best_10(final_topics,df,n=selected_number)
    st.write(f"you topics -> {top_topics}")
    st.write(final_df)
    df_xlsx = to_excel(final_df)
    st.download_button(label='📥 Download Current Topics', data=df_xlsx, file_name= f"{str(df)}_{we}_{ws}.xlsx")

                           
def to_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Sheet1')
    workbook = writer.book
    worksheet = writer.sheets['Sheet1']
    format1 = workbook.add_format({'num_format': '0.00'}) 
    worksheet.set_column('A:A', None, format1)  
    writer.close()
    processed_data = output.getvalue()
    return processed_data


def combine_similar_topics(final_topic_list_cleaned):
    # Vectorize the topics using TF-IDF
    vectorizer = TfidfVectorizer(stop_words="english")
    X = vectorizer.fit_transform(final_topic_list_cleaned)
    # Perform hierarchical clustering
    n_clusters = 10  # Number of main topics
    # clustering = AgglomerativeClustering(n_clusters=n_clusters, affinity='cosine', linkage='average')
    # cluster_assignments = clustering.fit_predict(X.toarray())

    # Perform DBSCAN clustering
    dbscan = DBSCAN(eps=0.6, min_samples=2, metric='cosine')
    cluster_assignments = dbscan.fit_predict(X.toarray())
    # Extract combined main topics
    unique_clusters = np.unique(cluster_assignments)
    st.write("unique_clusters",unique_clusters)
    if len(unique_clusters) <=1:
        return None
    else:
        main_topics = {}

        for cluster in unique_clusters:
            if cluster == -1:
                continue  # Ignore noise points (topics that do not belong to any cluster)

            indices = np.where(cluster_assignments == cluster)[0]
            cluster_topics = [final_topic_list_cleaned[i] for i in indices]
            main_topics[cluster] = cluster_topics

        # Display the combined main topics
        for cluster, topics in main_topics.items():
            st.write(f"Main Topic {cluster + 1}: {', '.join(topics)}")
            if len(topics) > 1500:
                main_topics[cluster]= topics[:1500]  

        
        prompt = "In the text delimited by triple backticks, there is a dictionary where the value for each key is a list of topics which are quite similar to each other. \
        #       Can you please provide one main topic for each key by combining the topics from the list of topics for that key.\
        #       The topic you provide from each list must be a maximum of 8 words.\
        #       Format your response as a list of topics separated by commas so the number of topics you provide is exactly equal to the number of keys\
        #       Text: ```{}``` \
        #      ".format(main_topics)
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            n=1
            )
        clean_topics = response['choices'][0]['message']['content']
        clean_topics_final = ast.literal_eval(clean_topics)

        return clean_topics_final



def generate_tags(msg, cleaned_topics_final):
    
    max_context_length = 1500
    if len(msg) > max_context_length:
        msg = msg[:max_context_length]
    
    
    try:
        prompt = f"""
        You will be provided with the following information:
        1. An arbitrary text sample. The sample is delimited with triple backticks.
        2. List of categories the text sample can be assigned to. The list is delimited with square brackets. The categories in the list are enclosed in the single quotes and comma separated.

        Perform the following tasks:
        1. Identify to which categories the provided text belongs to with the highest probability.
        2. Each text sample can be assigned to multiple categories based on the probabilities.
        3. If the text does not belong to any of the categories, then the response can be a blank string.
        3. Provide your response as a list. Do not provide any additional information except the list of topics each text is assigned to.

        List of categories: {cleaned_topics_final}

        Text sample: ```{msg}```

        """
      
        return (generate_chatgpt_response_v2(prompt))
    except:
        return ('')



def assign_final_topics_message(df_final,cleaned_topics_final):
    msg_unique = list(df_final.cleaned_message)
    tags = []

    progress_bar = st.progress(0)
    all_msg = len(msg_unique)
    count = 0 
    

    with st.spinner("Running...."):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            bar = st.progress(0)
            placeholder = st.empty()
            results = list(executor.map(generate_tags,msg_unique,[cleaned_topics_final] * len(msg_unique)))
            for idx,res in enumerate(results,start=1):
                progress = idx/all_msg
                placeholder.text(f"{int(progress * 100)}%")
                # update progress bar
                bar.progress(progress)

    df_final["final_topics"] = results
    return df_final


def create_binary_column(df_final,clean_topics_final):
    for top in clean_topics_final:
        df_final[top] = 0
    for top in clean_topics_final:
        for index, row in df_final.iterrows():
            rowtopics = row['final_topics']
            if top in rowtopics:
                df_final.loc[index, top] = 1
            else:
                continue
    return df_final






def main():
    with st.container():
        
        if "df_file" not in st.session_state:
            st.session_state.df_file = None
        
        if 'df' not in st.session_state:
            st.session_state.df = None
        
        if 'final_topics' not in st.session_state:
            st.session_state.final_topics = None
        
        if 'unique_topics_df' not in st.session_state:
            st.session_state.unique_topics_df = None
        
        if 'df_final' not in st.session_state:
            st.session_state.df_final = None

        if 'brand_name' not in st.session_state:
            st.session_state.brand_name = None

        if 'button' not in st.session_state:
            st.session_state.button = None

        if "name_file" not in st.session_state:
            st.session_state.name_file = None
        
        if "top_topics_show" not in st.session_state:
            st.session_state.top_topics_show= None

        if "all_data" not in st.session_state:
            st.session_state.all_data = None
        
        if "filter_data" not in st.session_state:
            st.session_state.filter_data = None
        
        
        # initialize our app
        left_column,right_column = st.columns(2)
        with left_column:
            df_file = st.file_uploader("Upload a Excel file")
            if df_file is None:
                st.warning("Please drop your excel file")
                st.warning("Please, if you encounter the -- AxiosError: Network Error--, close the excel you have open on your local machine")
                st.session_state.top_topics_show = None 
            else:
                st.session_state.df, uploaded_file_info, file_name = read_excel_parquet(df_file) #leitura
                st.session_state.all_data = True
                st.session_state.filter_data = True
                st.session_state.brand_name = file_name
                st.info(f"number of rows: {st.session_state.df.shape[0]}")
                if st.session_state.df is not None:
                    if  st.session_state.filter_data == True:
                        if st.checkbox("Filter data"):
                            st.session_state.all_data = False
                            if "author_predictions" not in st.session_state.df.columns:
                                ws,we,channel,brand = my_values_without_author(st.session_state.df,ws=True,we=True)
                                if channel == []:
                                    st.warning("Please select your channel")
                                if brand == []:
                                    st.warning("Please select your brand")
                                if brand !=[] and channel != []:
                                    try:
                                        st.session_state.df = filtering_without_author(st.session_state.df,channel,brand,ws,we)
                                        st.info(f"Data size : {st.session_state.df.shape[0]}")
                                        if st.button("Generate Topics"):
                                            st.session_state.button = True
                                            st.session_state.df = get_topics(st.session_state.df)
                                            st.session_state.final_topics = unique_topics(st.session_state.df)
                                            st.session_state.unique_topics_df = st.session_state.df
                                            if st.session_state.final_topics == []:
                                                st.error("does not have any topic/ Topics with less than 5 words/ Chat GPT API problem")
                                            if st.session_state.final_topics != [] :
                                                # removing the noise ( Topics with less than 5 words)
                                                st.session_state.final_topics = remove_noise_from_topics(st.session_state.final_topics)
                                                #combining the topics with an unsupervised model by sklearn
                                                cleaned_topics_final = combine_similar_topics(st.session_state.final_topics)
                                                if cleaned_topics_final == None:
                                                    st.error("You do not have more than 1 topic, change the filter used or perhaps the data uploaded.")
                                                else:
                                                    st.write("cleaned_topics")
                                                    st.write(cleaned_topics_final)
                                                    #assign each message to a cluster using threathing
                                                    st.session_state.df_final= assign_final_topics_message(st.session_state.df,cleaned_topics_final)
                                                    # create a binary column for each of the top 10 Topics
                                                    st.session_state.df_final = create_binary_column(st.session_state.df_final,cleaned_topics_final)
                                                    st.write("final data frame")
                                                    st.write(st.session_state.df_final.head())
                                                    #getting the best 10 topics
                                                    #top_topics,st.session_state.df_final = best_10(st.session_state.final_topics,st.session_state.df)
                                                    #st.session_state.top_topics_show = top_topics
                                                    st.session_state.name_file = f"_{ws}_{we}"
                                        else:
                                            st.warning("please click in the button -> Generate topics")
                                    except ZeroDivisionError as e:
                                        st.warning("Please check the calendar or check if your filter contains enough information") 
                            
                            if "author_predictions" in st.session_state.df.columns:
                                ws,we,author,channel,brand = my_values_filtered(st.session_state.df)
                                if author == [] :
                                    st.warning("please select your authors or All for all the authors")
                                if channel == []:
                                    st.warning("please select your channels or All for all channels")
                                if brand == []:
                                    st.warning("please select your brands or All for all brands") 
                                if author != [] and channel !=[] and brand !=[]:
                                    try:
                                        st.session_state.df = filtering(st.session_state.df,ws,we,author,channel,brand)
                                        st.info(f"number of rows: {st.session_state.df.shape[0]}")
                                        if st.button("Generate Topics"):
                                            st.session_state.button = True
                                            st.session_state.df = get_topics(st.session_state.df)
                                            st.session_state.final_topics = unique_topics(st.session_state.df)
                                            st.session_state.unique_topics_df = st.session_state.df
                                            if st.session_state.final_topics == []:
                                                st.error("does not have any topic/ Topics with less than 5 words/ Chat GPT API problem")
                                            if st.session_state.final_topics != [] :
                                                # removing the noise ( Topics with less than 5 words)
                                                st.session_state.final_topics = remove_noise_from_topics(st.session_state.final_topics)
                                                #combining the topics with an unsupervised model by sklearn
                                                cleaned_topics_final = combine_similar_topics(st.session_state.final_topics)
                                                if cleaned_topics_final == None:
                                                    st.error("You do not have more than 1 topic, change the filter used or perhaps the data uploaded.")
                                                else:
                                                    st.write("cleaned_topics")
                                                    st.write(cleaned_topics_final)
                                                    #assign each message to a cluster using threathing
                                                    st.session_state.df_final= assign_final_topics_message(st.session_state.df,cleaned_topics_final)
                                                    # create a binary column for each of the top 10 Topics
                                                    st.session_state.df_final = create_binary_column(st.session_state.df_final,cleaned_topics_final)
                                                    st.write("final data frame")
                                                    st.write(st.session_state.df_final.head())
                                                    #getting the best 10 topics
                                                    #top_topics,st.session_state.df_final = best_10(st.session_state.final_topics,st.session_state.df)
                                                    #st.session_state.top_topics_show = top_topics
                                                    st.session_state.name_file = f"_{ws}_{we}"
                                        else:
                                            st.warning("please click in the button -> Generate topics")
                                    except ZeroDivisionError as e:
                                        st.warning("Please check the calendar or check if your filter contains enough information") 
                    
                    if st.session_state.all_data == True:
                        if st.checkbox("All data"):
                            st.session_state.filter_data = False
                            if "author_predictions" not in st.session_state.df.columns:
                                channel,brand  = my_values_without_author(st.session_state.df)
                                if channel != [] and brand !=[]:
                                    try:
                                        st.session_state.df = filtering_without_author(st.session_state.df,channel,brand,ws=None,we=None)
                                        ws=0
                                        we = 0 
                                        st.info(f"Number of rows: {st.session_state.df.shape[0]}")
                                        if st.button("Generate Topics"):
                                            st.session_state.button = True
                                            st.session_state.df = get_topics(st.session_state.df)
                                            st.session_state.final_topics = unique_topics(st.session_state.df)
                                            st.session_state.unique_topics_df = st.session_state.df
                                            if st.session_state.final_topics == []:
                                                st.error("does not have any topic/ Topics with less than 5 words/ Chat GPT API problem")
                                            if st.session_state.final_topics != []: 
                                                # removing the noise ( Topics with less than 5 words)
                                                st.session_state.final_topics = remove_noise_from_topics(st.session_state.final_topics)
                                                #combining the topics with an unsupervised model by sklearn
                                                cleaned_topics_final = combine_similar_topics(st.session_state.final_topics)
                                                if cleaned_topics_final == None:
                                                    st.error("You do not have more than 1 topic, change the filter used or perhaps the data uploaded.")
                                                else:
                                                    st.write("cleaned_topics")
                                                    st.write(cleaned_topics_final)
                                                    #assign each message to a cluster using threathing
                                                    st.session_state.df_final= assign_final_topics_message(st.session_state.df,cleaned_topics_final)
                                                    # create a binary column for each of the top 10 Topics
                                                    st.session_state.df_final = create_binary_column(st.session_state.df_final,cleaned_topics_final)
                                                    st.write("final data frame")
                                                    st.write(st.session_state.df_final.head())
                                                    #getting the best 10 topics
                                                    #top_topics,st.session_state.df_final = best_10(st.session_state.final_topics,st.session_state.df)
                                                    #st.session_state.top_topics_show = top_topics
                                                    st.session_state.name_file = f"_All_data"
                                        else:
                                            st.warning("please click in the button -> Generate topics")
                                    except ZeroDivisionError as e:
                                        st.warning("Please check the calendar or check if your filter contains enough information") 
                            
                            if "author_predictions" in st.session_state.df.columns:
                                author,channel,brand = my_values_all(st.session_state.df)
                                if author != [] and channel !=[] and brand != []:
                                    try:
                                        st.session_state.df = filtering_all(st.session_state.df,author,channel,brand)
                                        st.info(f" number of rows: {st.session_state.df.shape[0]}")
                                        if st.button("Generate Topics"):
                                            st.session_state.button = True
                                            st.session_state.df = get_topics(st.session_state.df)
                                            st.session_state.final_topics = unique_topics(st.session_state.df)
                                            st.session_state.unique_topics_df = st.session_state.df
                                            if st.session_state.final_topics == []:
                                                st.error("does not have any topic/ Topics with less than 5 words/ Chat GPT API problem")
                                            if st.session_state.final_topics != []:
                                                  # removing the noise ( Topics with less than 5 words)
                                                st.session_state.final_topics = remove_noise_from_topics(st.session_state.final_topics)
                                                #combining the topics with an unsupervised model by sklearn
                                                cleaned_topics_final = combine_similar_topics(st.session_state.final_topics)
                                                if cleaned_topics_final == None:
                                                    st.error("You do not have more than 1 topic, change the filter used or perhaps the data uploaded.")
                                                else:
                                                    st.write("cleaned_topics")
                                                    st.write(cleaned_topics_final)
                                                    #assign each message to a cluster using threathing
                                                    st.session_state.df_final= assign_final_topics_message(st.session_state.df,cleaned_topics_final)
                                                    # create a binary column for each of the top 10 Topics
                                                    st.session_state.df_final = create_binary_column(st.session_state.df_final,cleaned_topics_final)
                                                    st.write("final data frame")
                                                    st.write(st.session_state.df_final.head())
                                                    #getting the best 10 topics
                                                    #top_topics,st.session_state.df_final = best_10(st.session_state.final_topics,st.session_state.df)
                                                    #st.session_state.top_topics_show = top_topics
                                                    st.session_state.name_file = f"_All_data"
                                        else:
                                            st.warning("please click in the button -> Generate topics")
                                    except ZeroDivisionError as e:
                                        st.warning("Please check the calendar") 



                  
                    if st.session_state.button is not None:
                        #if st.session_state.top_topics_show == None:
                            #st.warning("you do not have topics yet")
                        #else:
                            #st.write("your topics")
                            #st.write("\n")
                            #st.write(st.session_state.top_topics_show)
                            #st.write("Do you want to save or change the number of topics?")
                        if st.checkbox("Save"):
                            press = False
                            df_xlsx = to_excel(st.session_state.df_final)
                            if st.download_button(label='📥 Download Current Topics',
                            data=df_xlsx,
                            file_name= f"{st.session_state.brand_name}{st.session_state.name_file}.xlsx"):
                                press = True
                            
                            if press == True: 
                                st.write("save successful")
                            else:
                                st.warning("click on the download button to download") 
                        #if st.checkbox("Change topics"):
                            #press = False
                            #number_options = list(range(1,11))
                            #selected_number = st.selectbox("Num of topics",number_options)
                            #top_topics,final_df = best_10(st.session_state.final_topics,st.session_state.unique_topics_df,n=selected_number)
                            #st.write("your topics")
                            #st.write("\n")
                            #st.write(top_topics)
                            #df_xlsx = to_excel(final_df)
                            #if st.download_button(label='📥 Download Current Topics', 
                            #                      data=df_xlsx, file_name=  f"{st.session_state.brand_name}{st.session_state.name_file}_{selected_number}_topics.xlsx"):
                            #    press = True
                            #if press == True:
                            #    st.write("save successful")
                            #else:
                            #    st.warning("click on the download button to download")



                    
if __name__=="__main__":
    main()   
    
    




    
   
