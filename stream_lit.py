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



#Getting the API_Keys
#load_dotenv()
#api_key = os.getenv('API_Keys')

api_key = st.secrets["API_KEY"]
openai.api_key= api_key

#page config
st.set_page_config(page_title="BrandDelta_app",page_icon="💵",layout="wide")

st.title("Brand Delta Topic Modelling")



@st.cache(allow_output_mutation=True,suppress_st_warning=True) 
def read_excel(df_file):
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
        
    st.write(author)
    st.write(channel)
    return ws,we,author,channel,brand



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
        except:
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
        
        # initialize our app
        left_column,right_column = st.columns(2)
        with left_column:
            df_file = st.file_uploader("Upload a Excel file")
            if df_file is None:
                st.warning("Please drop your brand file")
                st.warning("Please, if you encounter the -- AxiosError: Network Error--, close the excel you have open on your local machine")
            else:
                st.session_state.df, uploaded_file_info, file_name = read_excel(df_file) #leitura
                st.session_state.brand_name = file_name
                st.info(f"number of rows: {st.session_state.df.shape[0]}")
                if st.session_state.df is not None:
                    if st.checkbox("Filter data"):
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
                                            top_topics,st.session_state.df_final = best_10(st.session_state.final_topics,st.session_state.df)
                                            st.write("your topics")
                                            st.write("\n") 
                                            st.write(top_topics)
                                            st.write("Do you want to change the topics or Save ?")
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
                                            top_topics,st.session_state.df_final = best_10(st.session_state.final_topics,st.session_state.df)
                                            st.write("your topics")
                                            st.write("\n") 
                                            st.write(top_topics)
                                            st.write("Do you want to change the topics or Save ?")
                                            st.session_state.name_file = f"_{ws}_{we}"
                                    else:
                                        st.warning("please click in the button -> Generate topics")
                                except ZeroDivisionError as e:
                                    st.warning("Please check the calendar or check if your filter contains enough information") 
                    if st.checkbox("All data"):
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
                                            top_topics,st.session_state.df_final = best_10(st.session_state.final_topics,st.session_state.df)
                                            st.write("your topics")
                                            st.write("\n") 
                                            st.write(top_topics)
                                            st.write("Do you want to change the topics or Save ?")
                                            st.session_state.name_file = f"_All_data"
                                    else:
                                        st.warning("please click in the button -> Generate topics")
                                except ZeroDivisionError as e:
                                    st.warning("Please check the calendar or check if your filter contains enough information") 
                        
                        if "author_predictions" in st.session_state.df.columns:
                            author,channel,brand = my_values_all(st.session_state.df)
                            if author != [] and channel !=[]:
                                try:
                                    st.session_state.df = filtering_all(st.session_state.df,author,channel,brand)
                                    st.info(f" number of rows: {st.session_state.df.shape[0]}")
                                    if st.button("Generate Topics"):
                                        st.session_state.df = get_topics(st.session_state.df)
                                        st.session_state.final_topics = unique_topics(st.session_state.df)
                                        st.session_state.unique_topics_df = st.session_state.df
                                        if st.session_state.final_topics == []:
                                            st.error("does not have any topic/ Topics with less than 5 words/ Chat GPT API problem")
                                        if st.session_state.final_topics != []:
                                            top_topics,st.session_state.df_final = best_10(st.session_state.final_topics,st.session_state.df)
                                            st.write("your topics")
                                            st.write("\n") 
                                            st.write(top_topics)
                                            st.write("Do you want to change the topics or Save ?")
                                            st.session_state.name_file = f"_All_data"
                                    else:
                                        st.warning("please click in the button -> Generate topics")
                                except ZeroDivisionError as e:
                                    st.warning("Please check the calendar") 


                # saving process
                    st.write("your topics")
                    st.write("\n") 
                    st.write(top_topics)
                    if st.session_state.button is not None:
                        if st.checkbox("Save"):
                            df_xlsx = to_excel(st.session_state.df_final)
                            st.download_button(label='📥 Download Current Topics',
                            data=df_xlsx,
                            file_name= f"{st.session_state.brand_name}{st.session_state.name_file}.xlsx")
                            st.write("save successful")
                        if st.checkbox("Change topics"):
                            number_options = list(range(1,11))
                            selected_number = st.selectbox("Num of topics",number_options)
                            top_topics,final_df = best_10(st.session_state.final_topics,st.session_state.unique_topics_df,n=selected_number)
                            st.write("your topics")
                            st.write("\n")
                            st.write(top_topics)
                            df_xlsx = to_excel(final_df)
                            st.download_button(label='📥 Download Current Topics', data=df_xlsx, file_name=  f"{st.session_state.brand_name}{st.session_state.name_file}_{selected_number}_topics.xlsx")




                    
if __name__=="__main__":
    main()   
    
    




    
   
