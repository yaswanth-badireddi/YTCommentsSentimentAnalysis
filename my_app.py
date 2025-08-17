import streamlit as st
import pandas as pd
import csv
import time
from googleapiclient.discovery import build
import google.generativeai as genai
import re
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import os

load_dotenv() 


genai.configure(api_key=os.getenv("GEMINI_API_KEY"))



def scrape_youtube_comments(url, api_key, max_comments=100):
    # Extract video ID from URL
    video_id_match = re.search(r"v=([a-zA-Z0-9_-]{11})", url)
    if not video_id_match:
        print("❌ Invalid YouTube URL")
        return None
    video_id = video_id_match.group(1)

    youtube = build('youtube', 'v3', developerKey=api_key)
    comments = []
    next_page_token = None

    while len(comments) < max_comments:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=100,
            pageToken=next_page_token
        )
        response = request.execute()

        for item in response['items']:
            snippet = item['snippet']['topLevelComment']['snippet']
            comments.append({
                'Author': snippet['authorDisplayName'],
                'Comment': snippet['textDisplay']
            })
            if len(comments) >= max_comments:
                break

        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break

    filename = 'sample.csv'
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Author', 'Comment'])
        writer.writeheader()
        writer.writerows(comments)

    print(f"✅ Extracted {len(comments)} comments and saved to {filename}")
    return filename

    

def classify_batch_with_gemini(comments):
    comment_block = "\n".join([f"{i+1}. {comment}" for i, comment in enumerate(comments)])

    prompt = f"""
You are a sentiment classifier. Classify each of the following Telugu or Telugu-English (code-mixed) YouTube comments as either:

- Good (positive/neutral)
- Bad (negative/abusive/offensive/harsh)

Respond with a numbered list of labels ("Good" or "Bad") corresponding to each comment in order.

Comments:
{comment_block}

Return format:
1. Good
2. Bad
3. Good
... and so on.
"""

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)

        response_text = response.text.strip()

        lines = response_text.splitlines()
        labels = []

        for line in lines:
            match = re.search(r'\d+\.\s*(Good|Bad)', line, re.IGNORECASE)
            if match:
                labels.append(match.group(1).capitalize())
        
        return labels
    except Exception as e:
        print(f"Error processing comments: {e}")
        return ["Unknown"] * len(comments)




def process_comments(batch_size=50):
    df = pd.read_csv('sample.csv')
    all_comments = df['Comment'].tolist()
    sentiments = []

    for i in range(0, len(all_comments), batch_size):
        batch = all_comments[i:i+batch_size]
        batch_labels = classify_batch_with_gemini(batch)
        sentiments.extend(batch_labels)

    if len(sentiments) < len(all_comments):
        sentiments += ["Unknown"] * (len(all_comments) - len(sentiments))

    df['Sentiment'] = sentiments
    df.to_csv('labeled_comments.csv', index=False, encoding='utf-8')
    return df


def display_sentiment_bar_chart():
    try:
        df = pd.read_csv('labeled_comments.csv')
        sentiment_counts = df['Sentiment'].value_counts()
        total = sentiment_counts.sum()

        percentages = (sentiment_counts / total) * 100

        fig, ax = plt.subplots()
        bars = ax.bar(percentages.index, percentages.values, color=['green', 'red', 'gray'])

        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.1f}%',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom')

        ax.set_ylabel('Percentage')
        ax.set_title('Sentiment Distribution: Good vs Bad')
        st.pyplot(fig)
    except Exception as e:
        st.error(f"Error generating bar chart: {e}")


    

def main():
    you_api_key=os.getenv("YOUTUBE_API_KEY")
    st.title('YouTube Comment Scraper and Sentiment Analysis')
    st.subheader('Scrape YouTube Comments and Classify Them as Good or Bad')
    youtube_url = st.text_input("Enter YouTube Video URL", "https://www.youtube.com/watch?v=IOopJ-PDpac")
    No_comments=st.text_input("Enter Number of comments","50") 

    if st.button('Scrape Comments'):
        if youtube_url:
            try:
               num_comments = int(No_comments)
               st.text('Scraping YouTube comments...')
               filename = scrape_youtube_comments(youtube_url, you_api_key, num_comments)
               st.success(f'Comments have been scraped and saved to {filename}')
            except ValueError:
               st.error("Please enter a valid integer for the number of comments.")
        else:
            st.warning('Please enter a valid YouTube video URL.')

    if st.button('Classify Comments'):
        st.text('Classifying comments as Good or Bad...')
        df = process_comments()
        st.success('Classification completed!')
        st.subheader('Classified Comments')
        st.write(df)
        display_sentiment_bar_chart()
        st.download_button(
            label="Download Classified Comments",
            data=df.to_csv(index=False).encode('utf-8'),
            file_name='labeled_comments.csv',
            mime='text/csv'
        )


if __name__ == '__main__':
    main()