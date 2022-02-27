'''
Created on Feb 24, 2022

@author: tiff
'''
import contentcreatormanager.media.video.video
import pytube
import os.path
import random
import ffmpeg
import time
import contentcreatormanager.platform.youtube
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


class YouTubeVideo(contentcreatormanager.media.video.video.Video):
    '''
    classdocs
    '''
    
    BASE_URL = "https://www.youtube.com/watch?v="
    
    MAX_RETRIES = 25
    
    #Private method to download a YouTube Video with pytube
    def __pytube_download(self, overwrite):
        #set variables for file name and path
        file_name = os.path.basename(self.file)
        file_path = self.file
        self.logger.info(f"Downloading {file_name}")
        
        #check for the file so redownload can be avoided unless overwrite is set to true
        if os.path.isfile(file_path):
            self.logger.info(f"File {file_name} already exists.")
            if overwrite:
                self.logger.info("Overwrite set removing file re-downloading")
                os.remove(self.file)
            else:
                self.logger.info("Overwrite not set not downloading")
                return
        
        self.logger.info(f"Attempting to download video portion of {self.title}")
        video_file = None
        vid = self.pytube_obj
        finished = False
        tries = 0
       
        #pytube has weird transient failures that you just keep trying and things work so this loop does that to a point for the video
        while not finished and tries < YouTubeVideo.MAX_RETRIES + 2:
            try:
                video_file = vid.streams.order_by('resolution').desc().first().download(filename_prefix="video_")
                finished = True
            except Exception as e:
                if tries > YouTubeVideo.MAX_RETRIES:
                    self.logger.error("Too many failed download attempts raising new exception")
                    raise Exception()
                self.logger.error(f"got error:\n{e}\nGoing to try again")
                tries += 1
                self.logger.info(f"Attempted {tries} time(s) of a possible {YouTubeVideo.MAX_RETRIES}")
                finished = False
        
    
        self.logger.info(f"Downloaded video for {self.title}")
        
        self.logger.info(f"Attempting to download audio portion of {self.title}")
        #pytube has weird transient failures that you just keep trying and things work so this loop does that to a point for the audio
        finished = False
        tries = 0
        while not finished and tries < YouTubeVideo.MAX_RETRIES + 2:
            try:
                audio_file = vid.streams.filter(only_audio=True).order_by('abr').desc().first().download(filename_prefix="audio_") 
                finished = True
            except Exception as e:
                if tries > YouTubeVideo.MAX_RETRIES:
                    self.logger.error("Too many failed download attempts raising new exception")
                    raise Exception()
                self.logger.error(f"got error:\n{e}\nGoing to try again")
                tries += 1
                self.logger.info(f"Attempted {tries} time(s) of a possible {YouTubeVideo.MAX_RETRIES}")
                finished = False
        
        self.logger.info(f"Downloaded audio for {self.title}")
        
        audFile = None
        vidFile = None
        source_audio = None
        source_video = None
        
        #preps things to ffmpeg the audio and video together
        finished = False
        tries = 0
        while not finished and tries < YouTubeVideo.MAX_RETRIES + 2:
            try:
                self.logger.info("Attempting to prep source audio and video to merge")
                source_audio = ffmpeg.input(audio_file)
                source_video = ffmpeg.input(video_file)
                audFile = self.getInputFilename(source_audio)
                vidFile = self.getInputFilename(source_video)
                finished = True
            except Exception as e:
                if tries > self.MAX_RETRIES:
                    self.logger.error("Too many failed download attempts raising new exception")
                    raise Exception()
                self.logger.error(f"got error:\n{e}\nGoing to try again")
                tries += 1
                self.logger.info(f"Attempted {tries} time(s) of a possible {self.MAX_RETRIES}")
                finished = False
        
        self.logger.info(f"Attempting to merge {vidFile} and {audFile} together as {file_name}")
        finished = False
        tries = 0
        
        #FFMPEG is used to combine the audio and video files
        while not finished and tries < self.MAX_RETRIES + 2:
            try:
                self.logger.info("Attempting to merge audio and video")
                ffmpeg.concat(source_video, source_audio, v=1, a=1).output(self.file).run()
                finished = True
            except Exception as e:
                if tries > self.MAX_RETRIES:
                    self.logger.error("Too many failed download attempts raising new exception")
                    raise Exception()
                self.logger.error(f"got error:\n{e}\nGoing to try again")
                tries += 1
                self.logger.info(f"Attempted {tries} time(s) of a possible {YouTubeVideo.MAX_RETRIES}")
                finished = False
                
        self.logger.info(f"Files merged as {file_name}")
    
        #cleanup the audio and video files
        self.logger.info("Cleaning up source files....")
        self.logger.info(f"Removing {audFile}")
        os.remove(audFile)
        self.logger.info(f"Removing {vidFile}")
        os.remove(vidFile)
    
    #private Method to run a video.list on the object using id
    def __get_web_data(self):
        request = self.channel.service.videos().list(
            part="snippet,contentDetails,statistics,status",
            id=self.id
        )
        result = request.execute()
        
        return result['items'][0]
  
    #Private method that just checks for the file'e existance
    def __is_downloaded(self):
        return os.path.isfile(self.file)
    
    #Private Method to construct a filename that is valid from the title
    def __file_name(self):
        valid_chars = '`~!@#$%^&+=,-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        getVals = list([val for val in f"{self.title}.mp4" if val in valid_chars])
        return "".join(getVals)
    
    #Private Method to get a pytube YouTube object for this video
    def __get_pytube(self, use_oauth=True):
        url = f"{YouTubeVideo.BASE_URL}{self.id}"
        return pytube.YouTube(url, use_oauth=use_oauth)
    
    #Slightly modified version of method on the google example git hub to initialize an upload
    def __initialize_upload(self):
        self.logger.info(f"Preparing to upload video to youtube with title: {self.title} ad other stored details")
        body=dict(
            snippet=dict(
                title=self.title,
                description=self.description,
                tags=self.tags,
                categoryId=self.category_id,
                defaultLanguage=self.default_language
            ),
            status=dict(
                embeddable=self.embeddable,
                license=self.license,
                privacyStatus=self.privacy_status,
                publicStatsViewable=self.public_stats_viewable,
                selfDeclaredMadeForKids=self.self_declared_made_for_kids
            )
        )
        self.logger.info("Starting the upload")
        # Call the API's videos.insert method to create and upload the video.
        insert_request = self.channel.service.videos().insert(
            part=','.join(body.keys()),
            body=body,
            # The chunksize parameter specifies the size of each chunk of data, in
            # bytes, that will be uploaded at a time. Set a higher value for
            # reliable connections as fewer chunks lead to faster uploads. Set a lower
            # value for better recovery on less reliable connections.
            #
            # Setting 'chunksize' equal to -1 in the code below means that the entire
            # file will be uploaded in a single HTTP request. (If the upload fails,
            # it will still be retried where it left off.) This is usually a best
            # practice, but if you're using Python older than 2.6 or if you're
            # running on App Engine, you should set the chunksize to something like
            # 1024 * 1024 (1 megabyte).
            media_body=MediaFileUpload(self.file, chunksize=-1, resumable=True)
        )
        self.logger.info("returning resumable_upload private method to create a resumable upload")
        return self.__resumable_upload(insert_request)
    
    #Slightly modified version of google example code for a resumable upload to youtube
    def __resumable_upload(self, request):
        response = None
        error = None
        retry = 0
        vidID = None
        while response is None:
            try:
                self.logger.info('Uploading file...') 
                response = request.next_chunk()
                if(response is not None):
                    if('id' in response):
                        self.logger.info(f"Video id \"{response['id']}\" was successfully uploaded.")
                        vidID = response['id']
                    else:
                        self.logger.warning(f"The upload failed with an unexpected response: {response}")
                        return
            except HttpError as e:
                if e.resp.status in contentcreatormanager.platform.youtube.YouTube.RETRIABLE_STATUS_CODES:
                    error = f"A retriable HTTP error {e.resp.status} occurred:\n{e.content}"
                else:
                    raise e
            except contentcreatormanager.platform.youtube.YouTube.RETRIABLE_EXCEPTIONS as e:
                error = f"A retriable error occurred: {e}"

            if error is not None:
                print(error)
                retry += 1
                if retry > YouTubeVideo.MAX_RETRIES:
                    exit('No longer attempting to retry.')

                max_sleep = 2 ** retry
                sleep_seconds = random.random() * max_sleep
                self.logger.info(f"Sleeping {sleep_seconds} seconds and then retrying...")
                time.sleep(sleep_seconds)
        self.logger.info(f"setting ID to {vidID}")
        self.id = vidID
    
    #Constructor
    def __init__(self, channel, ID : str = None, favorite_count : str ='0', comment_count : str ='0', dislike_count : str ='0', like_count : str ='0',
                 view_count : str ='0', self_declared_made_for_kids : bool =False, made_for_kids : bool =False, public_stats_viewable : bool =True,
                 embeddable : bool =True, lic : str ='youtube', privacy_status : str ="public", upload_status : str ='notUploaded',
                 has_custom_thumbnail : bool =False, content_rating : dict ={}, licensed_content : bool =False, 
                 default_audio_language : str ='en-US', published_at=None, channel_id=None, title=None, description=None, file_name : str = '', update_from_web : bool = False,
                 thumbnails : dict ={}, channel_title=None, tags : list =[], category_id : int =22, live_broadcast_content=None, new_video : bool =False):
        '''
        Constructor
        '''
        self.title = title
        super(YouTubeVideo, self).__init__(settings=channel.settings,ID=ID,file_name=file_name)
        self.logger = self.settings.YouTube_logger
        
        self.logger.info("Initializing Video Object as a YouTube Video Object")
        
        self.channel = channel
        
        self.published_at = published_at
        self.channel_id = channel_id
        self.title = title
        self.description = description
        self.thumbnails = thumbnails
        self.channel_title = channel_title
        self.tags = tags
        self.category_id = category_id
        self.live_broadcast_content = live_broadcast_content
        self.default_audio_language = default_audio_language
        self.default_language = default_audio_language
        self.licensed_content = licensed_content
        self.content_rating = content_rating
        self.has_custom_thumbnail = has_custom_thumbnail
        self.upload_status = upload_status
        self.privacy_status = privacy_status
        self.license = lic
        self.embeddable = embeddable
        self.public_stats_viewable = public_stats_viewable
        self.made_for_kids = made_for_kids
        self.self_declared_made_for_kids = self_declared_made_for_kids
        self.view_count = view_count
        self.like_count = like_count
        self.dislike_count = dislike_count
        self.comment_count = comment_count
        self.favorite_count = favorite_count
        self.downloaded = self.__is_downloaded()
        
        #if the new_video flag is set we do not set the pytube object since we cant
        if new_video:
            self.pytube_obj = None
        #if it is not new it should be uploaded and we can make the pytube object
        else:
            self.pytube_obj = self.__get_pytube()
            if update_from_web:
                self.update_local()
            
        self.logger.info("YouTube Video Object initialized")
        
    #Method to call videos.delete to remove this video from youtube
    def delete_web(self):
        request = self.channel.service.videos().delete(
            id=self.id
        )
        result = request.execute()
        
        return result
    
    #Updates the Video on youtube based on local properties
    def update_web(self):
        current_web_status = self.__get_web_data()
        
        current_web_snippet = current_web_status['snippet']
        current_web_status = current_web_status['status']
    
        need_to_update=False
        
        update_snippet = {}
        update_snippet['categoryId']=self.category_id
        update_snippet['defaultLanguage']=self.default_language
        update_snippet['description']=self.description
        update_snippet['tags']=self.tags
        update_snippet['title']=self.title
        update_status = {}
        update_status['embeddable']=self.embeddable
        update_status['license']=self.license
        update_status['privacyStatus']=self.privacy_status
        update_status['publicStatsViewable']=self.public_stats_viewable
        update_status['selfDeclaredMadeForKids']=self.self_declared_made_for_kids
        
        if not (update_snippet == current_web_snippet and update_status == current_web_status):
            need_to_update = True
        
        if not need_to_update:
            self.logger.info("No need to update returning None")
            return None

        request = self.channel.service.videos().update(
            part='snippet,status',
            body=dict(
                snippet=update_snippet,
                status=update_status,
                id=self.id
            )
        )
        
        return request.execute()
    
    #Method to update local properties based on the results of a videos.list call
    def update_local(self):
        self.logger.info(f"Updating Video Object with id {self.id} from the web")
        
        video = self.__get_web_data()
        if 'tags' not in video['snippet']:
            tags = []
        else:
            tags = video['snippet']['tags']
        if 'description' not in video['snippet']:
            description = ""
        else:
            description = video['snippet']['description']
        if 'selfDeclaredMadeForKids' not in video['status']:
            self_declared_made_for_kids = False
        else:
            self_declared_made_for_kids = video['status']['selfDeclaredMadeForKids']
        if 'defaultAudioLanguage' not in video['snippet']:
            default_audio_language = 'en-US'
        else:
            default_audio_language = video['snippet']['defaultAudioLanguage']
    
        self.published_at = video['snippet']['publishedAt']
        self.channel_id = video['snippet']['channelId']
        self.title = video['snippet']['title']
        self.description = description
        self.thumbnails = video['snippet']['thumbnails']
        self.channel_title = video['snippet']['channelTitle']
        self.tags = tags
        self.category_id = video['snippet']['categoryId']
        self.live_broadcast_content = video['snippet']['liveBroadcastContent']
        self.default_audio_language = default_audio_language
        self.licensed_content = video['contentDetails']['licensedContent']
        self.content_rating = video['contentDetails']['contentRating']
        self.has_custom_thumbnail = video['contentDetails']['hasCustomThumbnail']
        self.upload_status = video['status']['uploadStatus']
        self.privacy_status = video['status']['privacyStatus']
        self.license = video['status']['license']
        self.embeddable = video['status']['embeddable']
        self.public_stats_viewable = video['status']['publicStatsViewable']
        self.made_for_kids = video['status']['madeForKids']
        self.self_declared_made_for_kids = self_declared_made_for_kids
        self.view_count = video['statistics']['viewCount']
        self.like_count = video['statistics']['likeCount']
        self.dislike_count = video['statistics']['dislikeCount']
        self.comment_count = video['statistics']['commentCount']
        self.favorite_count = video['statistics']['favoriteCount']
        self.downloaded = self.__is_downloaded()
        
        self.logger.info("Update from web complete")
        
    #Method to upload video to YouTube
    def upload(self):
        file = self.file
        
        try:
            self.logger.info(f"Attempting to upload {file}")
            self.__initialize_upload()
        except HttpError as e:
            raise e
        
        self.pytube_obj = self.__get_pytube()
        self.update_from_web()
    
    #Method to download the video from youtube
    def download(self, overwrite=False):
        self.__pytube_download(overwrite=overwrite)
        