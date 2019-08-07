import boto3
import json
import urllib
import os
from twilio.rest import Client
import cv2

print("Cold Start w/CV2")


TABLE_USERS = os.environ['UsersTable']
TABLE_IMAGES = os.environ['ImagesTable']
FACE_COLLECTION = os.environ['RekogFaceCollection']
SSMTWILIOCREDS = os.environ['SSMTwilioCreds']

rekognition = boto3.client('rekognition')
s3 = boto3.client('s3')  
dynamo = boto3.client('dynamodb')
ssm = boto3.client('ssm')

# Get twilio creds from SSM
secret = ssm.get_parameter(Name=SSMTWILIOCREDS, WithDecryption=True)
twCredentials = json.loads(secret["Parameter"]["Value"])
twNumber = twCredentials["twNumber"]
twAccountSid = twCredentials["twAccountSid"]
twAuthToken = twCredentials["twAuthToken"]


# --------------- Main handler ------------------

def lambda_handler(event, context):

    ocvversion=cv2.__version__
    print("OpenCV Version:")
    print(ocvversion)

    # print('Event: %s' % json.dumps(event))
    
    try:

        # Get the object from the event
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'])

        # Retrieve metadata on this object
        meta = metadata(bucket, key)

        # Get sender and image id from S3 objects metadata
        sender_number = meta['sendernumber']
        image_id = meta['imgid']


        # Get user json object
        user_record = get_user(TABLE_USERS, sender_number);
        #print('User: %s' % json.dumps(user_record))

        # Get current mode
        user_mode = _unmarshal_value(user_record['CurrentMode'])
        #print('Mode: %s' % user_mode)


        # Rekog Identify People
        if user_mode == 'w':
            response = identify_faces(bucket, key)

            if response:
                print('SF Response: %s' % response)
    

                if len(response['FaceMatches']):
                    matched_photo = response['FaceMatches'][0]['Face']['ExternalImageId']
                    sms_reply = 'That looks like ' + matched_photo

                else:
                    sms_reply = 'Nobody I know!'

            else:
                sms_reply = 'Is there even a face there?'
                print('No faces found in target photo')

            message_user(sender_number, sms_reply)


         # Rekog Detect Labels
        if user_mode == 'o':
            response = detect_labels(bucket, key)
            labels = response['Labels']

            # Limit to 10 labels
            labels = labels[:10]
            labels_string = ''
            sms_reply = ''

            for label in labels:
                labelName = label['Name']
                labelConfidence = label['Confidence']
                #labels_string += '\n' + labelName + ': ' + str(labelConfidence)
                labels_string += '\n' + labelName + ': ' + "{0:.2f}".format(labelConfidence)


            if labels_string:
                print('Stuff Detected: %s' % labels_string)
                sms_reply = 'Stuff Detected: %s' % labels_string

            else:
                sms_reply = 'No Stuff Detected'

            message_user(sender_number, sms_reply)
        
        # Rekog Anaylze Faces
        elif user_mode == 'f':
            
            response = analyze_faces(bucket, key)
            
            print(response)

            if response['FaceDetails']:

                # List to hold faces
                faces = []

                for face in response['FaceDetails']:

                    #print(face)

                    detected_attributes = []
                    sms_reply = ''

                    # Gender
                    if face['Gender'] and face['Gender']['Value']:
                        detected_attributes.append(face['Gender']['Value'])

                    # Age Range
                    age_range = 'Age Range: ' + str(face['AgeRange']['Low']) + ' - ' + str(face['AgeRange']['High'])
                    detected_attributes.append(age_range)

                    # Smile
                    if face['Smile'] and face['Smile']['Value']:
                        detected_attributes.append('Smiling')
                    else:
                        detected_attributes.append('Not Smiling')

                    # Eyeglasses
                    if face['Eyeglasses'] and face['Eyeglasses']['Value']:
                        detected_attributes.append('Wearing Glasses')
                    else:
                        detected_attributes.append('Not Wearing Glasses')

                    # Mustache
                    if face['Mustache'] and face['Mustache']['Value']:
                        detected_attributes.append('Mustachioed')

                    # Beard
                    if face['Beard'] and face['Beard']['Value']:
                        detected_attributes.append('Bearded')

                    # EyesOpen
                    if face['EyesOpen'] and face['EyesOpen']['Value']:
                        detected_attributes.append('Eyes Open')

                    # Emotions
                    detected_emotions = []
                    if face['Emotions']:
                        for emotion in face['Emotions']:
                            labelName = emotion['Type']
                            labelConfidence = emotion['Confidence']
                            if labelConfidence>80:
                                detected_emotions.append(labelName)
                        
                        emotion_string = ', '.join(detected_emotions)
                        detected_attributes.append(emotion_string)

                    # Mash them all together into a string for the sms response
                    detection_string = '\n'.join(detected_attributes)
                
                    faces.append(detection_string)                
                    
                face_results_string = '\n------\n'.join(faces)
                    

                sms_reply = 'Face Features:\n------\n%s' % face_results_string
                
                message_user(sender_number, sms_reply)

            else:
                message_user(sender_number, 'No Face Found')
            
            print(response)
        
        # Rekog Detect Text
        elif user_mode == 't':
            response = detect_text(bucket, key)
            text_detections = response['TextDetections']
            
            detection_string = ''
            sms_reply = ''

            for detection in text_detections:
                detected_text = detection['DetectedText']
                text_type = detection['Type']
            
                if text_type=='LINE':
                    detection_string += '\n' + str(detected_text)
                    
            if detection_string:
                print('Text Detected: %s' % detection_string)
                sms_reply = 'Text Detected: %s' % detection_string

            else:
                sms_reply = 'No Text Detected'

            message_user(sender_number, sms_reply)


    except Exception as e:  
        print(e)  


# --------------- Helper Functions to call Rekognition APIs, etc. ------------------

def metadata(bucket, key):
    return s3.head_object(Bucket=bucket, Key=key)['Metadata']

def get_user(users_table, pk):
    print(users_table)
    print(pk)
    return dynamo.get_item(TableName=users_table, Key={'PhoneNo':{'S': pk}})['Item']

def message_user(user_id, msg):
    twClient = Client(twCredentials["twAccountSid"], twCredentials["twAuthToken"])

    message = twClient.messages.create(
        to=user_id, 
        from_=twCredentials["twNumber"],
        body=msg)

def identify_faces(bucket, key):
    try:
        response = rekognition.search_faces_by_image(
        	CollectionId=FACE_COLLECTION,
    	    Image={"S3Object": {"Bucket": bucket, "Name": key}}
        )
        return response
    except:
        print("No faces")
        return False
    
def analyze_faces(bucket, key):
    response = rekognition.detect_faces(
    	Attributes=["ALL"],
    	Image={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    return response

def detect_text(bucket, key):
    response = rekognition.detect_text(Image={"S3Object": {"Bucket": bucket, "Name": key}})
    return response

def detect_labels(bucket, key):
    response = rekognition.detect_labels(Image={"S3Object": {"Bucket": bucket, "Name": key}})
    return response

def _unmarshal_value(node):
    if type(node) is not dict:
        return node

    for key, value in node.items():
        key = key.lower()
        if key == 'bool':
            return value
        if key == 'null':
            return None
        if key == 's':
            return value
        if key == 'n':
            if '.' in str(value):
                return float(value)
            return int(value)
        if key in ['m', 'l']:
            if key == 'm':
                data = {}
                for key1, value1 in value.items():
                    if key1.lower() == 'l':
                        data = [_unmarshal_value(n) for n in value1]
                    else:
                        if type(value1) is not dict:
                            return _unmarshal_value(value)
                        data[key1] = _unmarshal_value(value1)
                return data
            data = []
            for item in value:
                data.append(_unmarshal_value(item))
            return data