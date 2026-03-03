"""
Test script for youtube-transcript-api 0.3.1
"""

from youtube_transcript_api import YouTubeTranscriptApi

def test_transcript(video_id):
    print(f"\n{'='*60}")
    print(f"Testing transcript for video ID: {video_id}")
    print('='*60)
    
    try:
        # Method 1: Try to get English transcript directly (simplest)
        print("\n🔍 Trying direct English transcript...")
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
            print(f"✅ Found {len(transcript)} lines of English transcript")
            sample = ' '.join([item['text'] for item in transcript[:3]])
            print(f"Sample: {sample[:200]}...")
        except Exception as e:
            print(f"❌ No direct English transcript: {e}")
        
        # Method 2: List all available transcripts
        print("\n📋 Listing all available transcripts:")
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            for transcript in transcript_list:
                lang_info = f"  • {transcript.language} ({transcript.language_code})"
                if transcript.is_generated:
                    lang_info += " [auto-generated]"
                if transcript.is_translatable:
                    lang_info += " [translatable]"
                print(lang_info)
        except Exception as e:
            print(f"  Error listing transcripts: {e}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Test with your videos
    video_ids = [
        "bc-0DAUz1L0",  # Malaysia video
        "68JUxRH8AZo",  # Paris video
        "KrLPczO5luE",  # Modi video
    ]
    
    for video_id in video_ids:
        test_transcript(video_id)
        print("\n")