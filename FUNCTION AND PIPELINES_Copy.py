#!/usr/bin/env python
# coding: utf-8

# ## Aim: To extract calendar event information in a tabular format. (Non-API apporach)
# 
# ### STAGE 1:
# Download calendar .ics file from personal email.
# 
# Extract or get an instance of an event object to see what information (keys and values) is available for extraction.
# 
# ### STAGE 2:
# 
# Craft a script to extract required event information. Flag small events (8 or fewer attendees) for manual review to determine suitability for inclusion in the data repository. Review suitability of all other events after determination of main topics in stage 3.
# 
# ### STAGE 3: 
# Integration of LLMs / AI into the workflow to facilitate identification of topics discussed / theme of the recorded sessions and support determination of categories.
# 
# ### STAGE 4:
# Creation of a custom function pipelines for transforming the imported calender events into a tabular format with the required information readily accessible. 
# 
# ### STAGE 5
# If applicable, identify specific external / third party tools to automate movement of data between different processing steps i.e. if data moves external to the IDE. 
# 
# ### Overall evolving Process: 
# - Manually download the calendar as an .ics file
# - Import the calendar file into Jupyter Notebook
# - Extract information availble via event attributes into a dataframe
# - Transform the remaining relevant data that is housed in the container object generated by the event attribute 'extra', using custom code. Extract urls for the related: (i) video recordings, (ii) transcripts and (iii) chats and add to the dataframe.
# - Clean: remove duplicates, remove entries with no video.
# - Use custom Google App Scripts (Java Script) to extract transcripts from google doc links into specified locations in a google sheet.
# - Use of an "internal" LLM (DistilBart) to summarize the extracted transcripts.
# - Use of external AI tools (Gemini, ChatGPT) to identify main themes or topics discussed using the summaries.
# 

# ## STAGE 4
# # Functions and pipelines

# In[1]:


# Import required modules
import pandas as pd
import re
from ics import Calendar  # from the ics package, import the calendar class to handle icalendar data in python
from datetime import datetime   # from the datetime module, import the datetime class to create objects that represent dates and times, perform operations and format them for different outputs


# In[2]:


''' 
load_parse_v3 is a function that will permit the extraction of data from .ics google calendar files. 
The required content will be made accessible through calendar object attributes. The final output will be a dataframe.
Intended to be used with the standalone content team email and associated calendar i.e. where no filtering is required since each event
has been identified for logging.

Created: 13/July/2024

UPDATES:
- Handling of Nonetypes that occur if there is no orgnaizer and leads to errors
- Use of the attendees attribute to get guest count.
- ID changed to Source_ID

Inputs
calendar: calendar object created when file is read into the python workspace
year_start: start-date year, YYYY
month_start: start-date month, M (excluding leading zeros)
day_start: start-date day, D (excluding leading zeros)
year_end: end-date year, YYYY
month_end: end-date month, M (excluding leading zeros)
day_end: end-date day, D (excluding leading zeros)

version logs:
pandas = 2.2.1
ics (Python icalendar parser) = 0.7.2

'''

def load_parse_v3(calendar, year_start, month_start, day_start, year_end, month_end, day_end):
    
    start_date = datetime(year_start, month_start, day_start) #create datetime object for the start_date
    end_date = datetime(year_end, month_end, day_end) #create datetime object for the end_date 

    extracted_events=[]
    
    for event in calendar.events:   #use of the events attribute to get a list of events
        time = event.duration   
        time_seconds = time.total_seconds() # total_seconds() is an attribute of the event.duration object
        hours = time_seconds // 3600    #this returns the rounded down value or quotient
        mins = (time_seconds % 3600) // 60    #division of the remainder by 60 to find number of minutes (rounded down)

        if start_date.date() <= event.begin.datetime.date() <= end_date.date():  #use of 'begin' to extract date/time info for the event, followed by creation of a datetime object to which the date method is applied
            organizer_obj = event.organizer   #creation of an organizer object that includes the email address of the organizer
            if organizer_obj:
                guests = event.attendees
                email = organizer_obj.email   #extraction of the email address using the 'email' attribute
                extracted_events.append({
                    "Source_ID": event.uid, 
                    "Title": event.name,
                    "Date": event.begin.datetime.date(),
                    "Duration (hh:mm)": f"{int(hours)}:{int(mins)}",
                    "Organizer": email,
                    "Extra": event.extra,
                    "Count": len(guests)})                
            else:
                pass

    df = pd.DataFrame(extracted_events)
    return df


# In[3]:


'''
url_extraction_v2 will be used to extract urls for the various recordings. These are housed in the event.extra object / container generated 
i.e. there is no specified attribute for extraction from the event class itself or the generated event.extra object. 

Custom script is required.
First, a string containing either the video, chat or transcript is extracted. 
This is followed by extraction of the exact url for the video, chat or transcript from the previous string. 

Created: 12/July/2024

UPDATES:
Use of ZIP to combine the multiple if/else statements into one 'for loop' where simultaneuous looping over multiple targets is facilitated.

Inputs:
df = output from the load_parse function

version logs:
pandas = 2.2.1

'''

def url_extraction_v2(df):
    df['source_url'] = ''    # Initialize the new columns with empty strings
    df['video_url'] = ''
    df['sourceC_url'] = ''
    df['chat_url'] = ''
    df['sourceT_url'] = ''
    df['transcript_url'] = ''

    df['Extra'] = df['Extra'].astype(str) # event.extra creates a container object which must be converted to str for accesibility of contents
    
    source_regex = re.compile(r'video/mp4:https?://[^\s]+')  #Create a re object that represents the pattern that contains the video url
    sourceC_regex = re.compile(r'text/plain:https?://[^\s]+')
    sourceT_regex = re.compile(r'document:https?://[^\s]+')

    video_regex = re.compile(r'https?://drive[^\s]+') # Create a re object that represents the video url pattern
    chat_regex = re.compile(r'https?://[^\s]+')
    transcript_regex = re.compile(r'https?://[^\s]+')
    
    for index, row in df.iterrows():  #iterrows allows you to iterate over each row by index and row; each row is treated as a series, with the column names acting like key
        
        vid_strings = source_regex.findall(row['Extra'])   #Find all instances of the pattern in the row being considered; returns a series
        chat_strings = sourceC_regex.findall(row['Extra'])
        trans_strings = sourceT_regex.findall(row['Extra'])

        strings = [vid_strings, chat_strings, trans_strings]
        cols = ['source_url', 'sourceC_url', 'sourceT_url']
        placeholders = ['No video', 'No chat', 'No transcript']
        
        for col, string, placeholder in zip(cols, strings, placeholders):  #use zip in the for loop to allow looping over multiple targets simutaneously
            joined = ' , '.join(string or []) # defaults to an empty list if string is None
            df.at[index, col] = joined if joined else placeholder

    for index, row in df.iterrows():
        video_urls = video_regex.findall(row['source_url']) # row['source_url'] uses source_url as the key to pull that specific data.
        chat_urls = chat_regex.findall(row['sourceC_url'])
        transcript_urls = transcript_regex.findall(row['sourceT_url'])
        
        urls = [video_urls, chat_urls, transcript_urls]
        cols_2 = ['video_url', 'chat_url', 'transcript_url']

        for col, url, placeholder in zip(cols_2, urls, placeholders):
            joined_2 = ' , '.join(url or []) # defaults to an empty list if string is None
            df.at[index, col] = joined_2 if joined_2 else placeholder

    return df


# In[4]:


'''
clean_part1 is to be used to complete the first set of steps in the cleaning process before manual review of small events i.e. events
that may be personal or not meant for community sharing e.g. pod meetings, skill-up sessions etc.

Actions: (i) sorting by date, (ii) dropping rows with no video, (iii) dropping duplicates, (iv) dropping pod events.

Created: 13/July/2024

Inputs:
- df: table or dataframe from previous extraction steps

Version logs:
pandas = 2.2.1

'''

def clean_part1(df):
    # sort by date; defaults to ascending.
    df = df.sort_values(by='Date')
    # drop rows with no video recording
    no_video = df[df['source_url']=='No video'].index.tolist()
    df.drop(index=no_video, axis=0, inplace=True)
    # drop duplicates
    df = df.drop_duplicates()
    # drop pod or Pod meetings
    pods = df[df['Title'].str.contains(r'pod')].index.tolist()
    Pods = df[df['Title'].str.contains(r'Pod')].index.tolist()
    df.drop(index=pods, axis=0, inplace=True)
    df.drop(index=Pods, axis=0, inplace=True)

    return df
    


# In[5]:


'''
pause_for_manual_check is a function designed to introduce a pause in the pipeline and permit manual review of small events that may need
to be dropped.
Identified rows are manually entered and this is followed by dropping of these rows before execution of the remainder of the pipeline i.e.
clean_part2.

Created: 14/July/2024

Inputs
df: Table or dataframe from the first stage of cleaning.

Version logs:
pandas = 2.2.1
'''
def pause_for_manual_check(df):
    # Identifying small meetings that were likely personal or not meant for general community consumption
    print("Pause and review small groups")
    display(df[df['Count'] <= 8])
    # Drop rows
    rows=input("Add rows and press enter.(Separate with commas. No spaces)")
    rows=rows.split(',')
    index=[]
    for i in rows:
        i=int(i)
        index.append(i)
    df.drop(index, axis=0, inplace=True)
    return df


# In[6]:


'''
clean_part2 is to be used to complete the second set of steps in the cleaning process after manual review of small events i.e. events
that may be personal or not meant for community sharing e.g. pod meetings, skill-up sessions etc.

Actions: (i) drop unnecessary columns, (ii) add extra columns, (iii) order the columns, (iv) reset the index.

Created: 13/July/2024

Inputs:
- table_name: table or dataframe produced after manual review and deletion of "small" events.
- file_path: export file path including intended name of excel file (in quotes).

Version logs:
pandas = 2.2.1

'''

def clean_part2(df, file_path):
    # drop unnecessary columns
    df.drop(columns=['Extra', 'Count', 'source_url', 'sourceC_url', 'sourceT_url'], axis=1, inplace=True)
    # add extra needed columns 
    df['Topics'] = ''
    df['Type'] = ''
    df['Routing'] = ''
    df['ID'] = ''
    df['Transcript'] = ''
    df['Summary'] = ''
    # order the columns
    export = df[['ID', 'Source_ID', 'Title', 'Date', 'Duration (hh:mm)', 'Organizer', 'Topics', 'Type', 'Sub-Type', 'Routing', 'Comments', 'video_url',
                             'chat_url', 'transcript_url', 'Transcript', 'Summary']].copy()
    # reset the index
    export.reset_index(drop=True, inplace=True)
    # export file in excel format
    export.to_excel(file_path, index=False)
    
    return print('Exported!')


# ### Pipeline: Calendar data extraction, transformation and loading (local)
# #### (Historic)

# Each calendar ics file is imported to the python ecosystem where it is transformed by:
# - parsing to convert it from its raw format to a more structured format that can be further processed
# - extraction of information accessible via event attributes into a dataframe
# - use of custom script to extract additional information housed in the container generated by the event attribute "extra": (i) video recordings, (ii) transcripts and (iii) chats and add to the dataframe.
# 
# It is then cleaned before being exported (loading on Google drive):
# - dropping of duplicates
# - dropping of events without recordings
# - dropping of pod meetings
# - dropping of "small" events that have been manually verified as not relevant (during a pause of the pipeline)
# 

# In[14]:


# read the .ics file
with open('/Users/kerry-annharris/Documents/Startwise/2024/Projects/Content Management/WORKSPACE/Miriam.ics', 'r') as file:
    calendar1 = Calendar(file.read())

year_start=2024
month_start=1
day_start=1
year_end=2024
month_end=7
day_end=12

file_path = '/Users/kerry-annharris/Documents/Startwise/2024/Projects/Content Management/EXTRACTS/EXTRACTS_Miriam.xlsx'

# List of functions to apply in sequence
process_steps = [
    (load_parse_v3, {'year_start':year_start, 'month_start':month_start, 'day_start':day_start,
                     'year_end':year_end, 'month_end':month_end, 'day_end':day_end}),   # only key word arguments are listed i.e. not the input file
    (url_extraction_v2, {}),
    (clean_part1, {}),
    (pause_for_manual_check, {}),
    (clean_part2, {'file_path':file_path})]


# In[15]:


# Execute the function pipeline
df = calendar1
for step, kwargs in process_steps:
    df = step(df, **kwargs)


# ### Pipeline: Calendar data extraction, transformation and loading (local)
# #### (Ongoing - with independent content calendar)

# In[ ]:


# read the .ics file
# with open('/Users/kerry-annharris/Documents/Startwise/2024/Projects/Content Management/WORKSPACE/cressita.brewster@startwisebarbados.com.ics', 'r') as file:
#     calendar1 = Calendar(file.read())

year_start=2024
month_start=1
day_start=1
year_end=2024
month_end=7
day_end=12

file_path = '/Users/kerry-annharris/Documents/Startwise/2024/Projects/Content Management/EXTRACTS/EXTRACTS_Cressita.xlsx'

# List of functions to apply in sequence
process_steps = [
    (load_parse_v3, {'year_start':year_start, 'month_start':month_start, 'day_start':day_start,
                     'year_end':year_end, 'month_end':month_end, 'day_end':day_end}),   # only key word arguments are listed i.e. not the input file
    (url_extraction_v2, {}),
    (clean_part1, {}),
    (clean_part2, {'file_path':file_path})]


# In[ ]:


# Execute the function pipeline
df = calendar1
for step, kwargs in process_steps:
    df = step(df, **kwargs)


# ## Functions and pipeline for generating summaries from extracted transcripts

# In[7]:


# Import required libraries
from transformers import BartTokenizer, BartForConditionalGeneration
import re
import time


# 
# **DistilBART** is a distilled version of the BART (Bidirectional and Auto-Regressive Transformers) model. It is designed to be smaller, faster, and more efficient while maintaining a significant portion of BART's performance.
# - DistilBART is particularly well-suited for tasks like summarization, where it can generate concise summaries of longer texts.
# - It can also be used for other text generation tasks such as translation and text completion.
# 
# Ideal for applications where computational resources are limited, such as on mobile devices or in real-time applications.

# In[8]:


# Load the tokenizer and model for DistilBART
tokenizer = BartTokenizer.from_pretrained('sshleifer/distilbart-cnn-12-6')
model = BartForConditionalGeneration.from_pretrained('sshleifer/distilbart-cnn-12-6')


# In[9]:


'''
Function for tokenizing and splitting the transcripts into chunks.

Created: 23/July/2024

Inputs:
text = text to be tokenized and split. Can be a column from a dataframe.

Version logs:
pandas==2.2.2
transformers===4.38.2

'''

def split_into_chunks(text, max_length=1024):
    # Tokenize the text
    tokens = tokenizer.encode(text)
    # Split into chunks based on the max number of tokens permissible per processing cycle
    chunks = [tokens[i:i+max_length] for i in range(0, len(tokens), max_length)]
    # decode the chunks back to text
    return [tokenizer.decode(chunk, skip_special_tokens=True) for chunk in chunks]


# In[10]:


'''
Creation of a function to use split_into_chunks function with my dataset and incorporate into the pipeline or
workflow.

Created: 26/July/2024

Inputs:
df with extracted transcripts

Version logs:
pandas==2.2.2
transformers===4.38.2

'''

def get_chunks(df):
    if 'Chunks' not in df.columns:
        df['Chunks'] = '' # Add an empty column for the chunks
        
    df['Chunks'] = [split_into_chunks(row['Transcript']) for index, row in df.iterrows()]

    return df


# In[11]:


'''
Function for summarizing the chunks.

Created: 23/July/2024

Inputs:
text = text to be summarized. Can be a column from a dataframe.

Version logs:
pandas==2.2.2
transformers===4.38.2

'''

def summarize_text(text):
    # Convert the input text into tokens (numerical representations of the text that the model can understand)
    inputs = tokenizer(text, return_tensors='pt', truncation=True, max_length=1024)
    # Generate the summary
    summary_ids = model.generate(inputs['input_ids'], max_length=300, min_length=30, do_sample=False)
    # Decode Tokens back to readable string, excluding "special tokens"
    summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
    return summary
    


# In[12]:


'''
Function to summarize chunks in BATCHES to manage the computational load associated with using DistilBART for
text summarization. A pause between batches is included to help with computaional efficiency i.e. manage issue of 
over-heating etc. Progress messages are printed with each batch, along with a confirmation of file export.

Created: 28/July/2024

Inputs:
df with chunks in required column
file_path for exporting of updated data frame as an excel file (in quotes)
pause_duration represents the pause in seconds as e.g. 180 (=3 mins)

Version logs:
pandas==2.2.2
transformers===4.38.2

'''

def batch_sum(df, file_path, pause_duration):
    df['Summary'] = df['Summary'].astype(str)  # Explicitly stating the "str" datatype to avoid dtype errors when adding the summaries to the empty column
    
    batch_size = 10 if len(df) >= 10 else len(df)  # implicitly setting the batch size based on the size of the dataframe
    total_batches = len(df) // batch_size + (1 if len(df) % batch_size > 0 else 0)
    
    for i in range(0, len(df), batch_size):
        start_index = i
        # Avoid indexerror that would occur if the stop_index exceeds the the dataframe's length
        stop_index = min(i+batch_size, len(df))       # my initial thought was: if (i+batch_size)<len(df) else len(df) in list comprehension
        
        # Track batches being processed
        current_batch = (i // batch_size) + 1  # for example, if i = 0, current batch would be 1
        print (f"Processing batch {current_batch} of {total_batches}")
        
        for index, row in df.iloc[start_index:stop_index].iterrows():
            chunks = row['Chunks']
            summaries = [summarize_text(chunk) for chunk in chunks if chunk]
            combined_summaries = " ".join(summaries)    
            df.at[index, 'Summary'] = combined_summaries
        time.sleep(pause_duration) if stop_index < (len(df)-1) else None     # introducing a pause to manage computational load and risk of overheating etc.; passing skips the pause after the last batch
    df.to_excel(file_path, index=False)
    print ("File exported")


# ### Pipeline: Generation of summaries from extracted transcripts

# In[ ]:


# Define keyword arguments
file_path = '/Users/kerry-annharris/Documents/Startwise/2024/Projects/Content Management/EXTRACTS/SUMMARIES/SUMS_TEST_28-Jul.xlsx'
pause_duration = 180

# List of functions to apply in sequence with keyword arguments
process_steps_sum = [
    (preprocess_tscript, {}),
    (get_chunks, {}),
    (batch_sum, {'file_path':file_path, 'pause_duration':pause_duration})]


# In[ ]:


# Execute the function pipeline
df = pd.read_excel('/Users/kerry-annharris/Documents/Startwise/2024/Projects/Content Management/EXTRACTS/GSHEETS_FOR_TSCRIPTS/TEST.xlsx')
for step, kwargs in process_steps_sum:
    df = step(df, **kwargs)


# In[ ]:




