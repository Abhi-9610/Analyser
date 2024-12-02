from flask import Flask, jsonify, request, render_template
from googleapiclient.discovery import build
from flask_cors import CORS
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import re

app = Flask(__name__)
CORS(app)

# Replace with your actual API key
API_KEY = 'AIzaSyCD6JBIVlLKtue86oLnMrnRZifMFsaYgO8'
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

# Initialize the VADER sentiment analyzer
analyzer = SentimentIntensityAnalyzer()

# Function to fetch YouTube video details
def get_video_details(video_id):
    try:
        youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
        request = youtube.videos().list(
            part='snippet',
            id=video_id
        )
        response = request.execute()

        if not response.get('items'):
            raise ValueError("Video not found or API returned no results.")

        video_info = response['items'][0]['snippet']
        title = video_info['title']
        description = video_info['description']
        thumbnail_url = video_info['thumbnails']['high']['url']

        short_description = (description[:150] + '...') if len(description) > 150 else description

        return {
            'title': title,
            'thumbnail_url': thumbnail_url,
            'description': short_description
        }
    except Exception as e:
        print(f"Error fetching video details for ID {video_id}: {e}")
        raise ValueError("Could not fetch video details. Check if the video ID is correct.")


# Function to fetch YouTube comments with pagination
def get_youtube_comments(video_id, max_results=100):
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
    comments = []
    next_page_token = None

    while True:
        try:
            request = youtube.commentThreads().list(
                part='snippet',
                videoId=video_id,
                textFormat='plainText',
                maxResults=max_results,
                pageToken=next_page_token
            )
            response = request.execute()
            for item in response.get('items', []):
                comment = {
                    'text': item['snippet']['topLevelComment']['snippet']['textDisplay'],
                    'author': item['snippet']['topLevelComment']['snippet']['authorDisplayName'],
                    'likes': item['snippet']['topLevelComment']['snippet']['likeCount']
                }
                comments.append(comment)

            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
        except Exception as e:
            print(f"Error fetching comments: {e}")
            break

    return comments

# Function to analyze sentiment of comments using VADER
def analyze_sentiment(comments):
    positive_comments = []
    negative_comments = []
    neutral_comments = []

    for comment in comments:
        analysis = analyzer.polarity_scores(comment['text'])
        sentiment_score = analysis['compound']

        if sentiment_score >= 0.05:
            positive_comments.append(comment)
        elif sentiment_score <= -0.05:
            negative_comments.append(comment)
        else:
            neutral_comments.append(comment)

    total_comments = len(comments)
    positive_percentage = (len(positive_comments) / total_comments) * 100 if total_comments else 0
    negative_percentage = (len(negative_comments) / total_comments) * 100 if total_comments else 0
    neutral_percentage = (len(neutral_comments) / total_comments) * 100 if total_comments else 0

    # Sorting to get top 5 positive and negative comments
    top_positive = sorted(positive_comments, key=lambda x: analyzer.polarity_scores(x['text'])['compound'], reverse=True)[:5]
    top_negative = sorted(negative_comments, key=lambda x: analyzer.polarity_scores(x['text'])['compound'])[:5]

    result = {
        'positive_percentage': positive_percentage,
        'negative_percentage': negative_percentage,
        'neutral_percentage': neutral_percentage,
        'top_positive': top_positive,
        'top_negative': top_negative,
        'total_comments': total_comments
    }

    return result

# Function to extract video ID from a URL
def extract_video_id(url):
    print(f"Extracting video ID from URL: {url}")  # Debug statement
    regex = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=|shorts\/)|youtu\.be\/)([^"&?\/\s]{11})'
    match = re.search(regex, url)
    if match:
        video_id = match.group(1)
        print(f"Extracted video ID: {video_id}")  # Debug statement
        return video_id
    else:
        print("No valid video ID found.")  # Debug statement
        return None


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        video_url = request.form.get('video_id')
        video_id = extract_video_id(video_url)
        if not video_id:
            return render_template('index.html', error="Invalid YouTube URL. Please check the format.")

        try:
            video_details = get_video_details(video_id)
            if not video_details:
                raise ValueError("Could not fetch video details. Check if the video ID is correct.")
            
            comments = get_youtube_comments(video_id, max_results=100)
            if not comments:
                raise ValueError("No comments found for this video.")
            
            result = analyze_sentiment(comments)
            total_likes = sum(comment['likes'] for comment in comments)
            total_shares = len(comments)  # Example, adjust if needed

            return render_template('index.html', data=result, video_details=video_details, total_likes=total_likes, total_shares=total_shares)
        except Exception as e:
            return render_template('index.html', error=f"Error occurred: {e}")

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
