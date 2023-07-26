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

#Getting the API_Keys
load_dotenv()
api_key = os.getenv('API_Keys')
openai.api_key= api_key


#page config
st.set_page_config(page_title="BrandDelta_app",page_icon="💵",layout="wide")

@st.cache(allow_output_mutation=True) # trying no to be always rerruning the dataframe
def read_parquet(file_path):
    df =pd.read_parquet(file_path)
    return df

def my_values(df):
   #options
    #br_options = [x for x in df["brand"].unique()]
    author_options= [x for x in df["author_predictions"].unique()]
    channel_options= [x for x in df["message_type"].unique()]

    #creating the brand
    #br = st.selectbox("Select a brand:", br_options)
    #time period
    start_date = st.date_input("Select start date", value=datetime(2023, 7, 1))
    end_date =  st.date_input("Select end date", value=datetime(2023, 7, 1))
    #convert our dates
    ws = start_date.strftime('%Y-%m-%d')
    we = end_date.strftime('%Y-%m-%d')
    # author
    author =  st.multiselect("Select the author categories:", author_options)
    channel = st.multiselect("Select the channel categories:", channel_options)
    return ws,we,author,channel

def filtering(df,ws,we,author,channel):
    df = df[(df['Week Commencing'] >= ws) & (df['Week Commencing'] <= we) & (df["author_predictions"].isin(author)) & (df["message_type"].isin(channel))]
    alldata = ' '.join(df["cleaned_message"])
    lengpt = len(alldata) / 4000   #(because chatgot maximum token size is 4076)
    posts_to_combine = round(len(df) / lengpt)
    df['nposts'] = np.arange(len(df))//posts_to_combine+1
    df['grouped_message'] = df.groupby(['nposts'])['cleaned_message'].transform(lambda x: ' '.join(x))
    return(df)

# generating the Chat GPT respose
def generate_chatgpt_response_v2(prompt, model = "gpt-3.5-turbo"):
    time.sleep(7)
    responses = []
    restart_sequence = "\n"

    response = openai.ChatCompletion.create(
          model=model,
          messages=[{"role": "user", "content": prompt}],
          temperature=0,
          n=1
        )

    return response['choices'][0]['message']['content']


def get_topics(df):
    gr_msg_unique = list(df.grouped_message.unique())
    topics = []
    l=0
    for gm in gr_msg_unique:
        try:
            topics.append(generate_chatgpt_response_v2("Determine exactly 3 topics that are being discussed \
                                                    in the text delimited by triple backticks. \
                                                    Make each topic 5 to 6 words long. \
                                                    Format your response as a list of items separated by commas \
                                                    Text: ```{}``` \
                                                    ".format(gm)))
        except Exception as e:
            print(e)
            topics.append('')
        print(l)
        l+=1
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
    st.write(df2)
    return top_10_topics,df2
    # saving the data frame.
    #df2.to_excel(r"C:\Users\Technology\Desktop\tasks\text_summary\IT_findus_nov-june.xlsx", index=False)


def Topics_num(final_topics,df):
    number_options = list(range(1,11))
    selected_number = st.selectbox("Num of topics",number_options)
    top_topics,final_df = best_10(final_topics,df,n=selected_number)
    st.write(f"you topics -> {top_topics}")
    if st.checkbox("Save your df with your topics"):
        save_path = st.text_input("Write the absolute path for saving the file")
        final_df.to_excel(save_path, index=False)
        st.write("Congratulations, you saved you dataframe")


def main():
    with st.container():
        
        if 'df' not in st.session_state:
            st.session_state.df = None
        
        if 'final_topics' not in st.session_state:
            st.session_state.final_topics = None
        
        if 'unique_topics_df' not in st.session_state:
            st.session_state.unique_topics_df = None
        
        if 'df_final' not in st.session_state:
            st.session_state.df_final = None
    
    API_URL = 'https://api.openai.com/v1/playground'
    response = requests.post(API_URL, headers=headers, json=data)
    headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {api_key}'
    if response.status_code == 200:
        print("API key is working.")
        print("Response:")



        
        # initialize our app
        left_column,right_column = st.columns(2)
        with left_column:
            #market = st.text_input("Enter your market here")
            #path_name = f"C:\\Users\\BrunoMalta\\Brand Delta\\Food Pilot - General\\data\\modelled_data\\{market}\\Workflow_output\\latest_output"
            #file = glob.glob(path_name + "/*.parquet")
            df_file= st.file_uploader("Upload a Parquet file")
            if df_file is not None:
                # read our file
                st.session_state.df = pd.read_parquet(df_file)
                st.session_state.df['Week Commencing'] = st.session_state.df['created_time'].apply(lambda x: (x - timedelta(days=x.weekday())).replace(hour=0, minute=0, second=0, microsecond=0))
                st.write(st.session_state.df.shape)
            else:
                st.error("invalid data_path")
            if st.session_state.df is not None:
                ws,we,author,channel = my_values(st.session_state.df)
                st.session_state.df = filtering(st.session_state.df,ws,we,author,channel)
                st.write(st.session_state.df.shape)
                if st.button("Generate Topics"):
                    st.session_state.df = get_topics(st.session_state.df)
                    st.write(st.session_state.df)
                    st.session_state.final_topics = unique_topics(st.session_state.df)
                    st.session_state.unique_topics_df = st.session_state.df

                    if len(st.session_state.final_topics) == 0:
                        st.error("does not have any topic")
                    if st.session_state.df is not None :
                        top_topics,st.session_state.df_final = best_10(st.session_state.final_topics,st.session_state.df)
                        st.write(st.session_state.df_final)
                        st.write("your topics")
                        st.write("\n") 
                        st.write(top_topics)
                        st.write("Do you want to change the topics or Save ?")
                
    
                if st.checkbox("Save"):
                    save_path = st.text_input("Write the absolute path for saving the file")
                    type(st.write(save_path))
                    st.session_state.df_final.to_excel(save_path, index=False)
                    st.write("save successful")
                if st.checkbox("change topics"):
                    Topics_num(st.session_state.final_topics,st.session_state.unique_topics_df)



if __name__=="__main__":
    main()   
    
    




    
   
