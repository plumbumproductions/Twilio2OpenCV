import boto3
import json
import requests
import os
import uuid
import cv2

print("Cold Start")


# GLOBAL CONSTANTS
THUMB_DIMENSION = 640

TABLE_USERS = os.environ['UsersTable']
TABLE_IMAGES = os.environ['ImagesTable']

s3 = boto3.resource('s3')
S3_BUCKET = os.environ['ImagesBucket']
S3_PREFIX = os.environ['BucketNamePrefix']

def lambda_handler(event, context):

	# print('Event: %s' % json.dumps(event))

	record = event['Records'][0]
	eventName = record['eventName']

	if eventName=='INSERT': 

		newItemImage = record['dynamodb']['NewImage']

		mediaURLMarshalled = newItemImage['url']
		fromNumberMarshalled = newItemImage['user']
		imgIDMarshalled = newItemImage['ImgID']

		# GET SENDER NUMBER AND MEDIA URL FROM NEW VERSION OF RECORD
		mediaURL = _unmarshal_value(mediaURLMarshalled)
		senderNumber = str(_unmarshal_value(fromNumberMarshalled))
		imgID = _unmarshal_value(imgIDMarshalled)

		#print('Sender: %s' % senderNumber)
		#print('Image ID: %s' % imgID)
		#print('Media URL: %s' % mediaURL)

		# GENERATE A RANDOM BASE NAME FOR THE IMAGE AS STORED ON s3
		tempFilename = str(uuid.uuid4())
		tempFilePath = '/tmp/' + tempFilename
		#print(tempFilePath)

		# DOWNLOAD THE IMAGE AND SAVE TO TEMP
		r = requests.get(mediaURL)
		with open(tempFilePath, "wb") as imageHandle:
			imageHandle.write(r.content)
		#print(r.headers)

		# GET THE IMAGE TYPE SO WE CAN PUT THE RIGHT EXTENSION ON ITS NAME
		twilioContentType = r.headers['content-type']
		#print(r.headers['content-type'])

		# IF THE FILE NOW EXISTS LOCALLY...
		if os.path.exists(tempFilePath):

			#print("The file exists!")

			# FINISH FILE NAME WITH EXTENSION BASED ON MIME TYPE
			if twilioContentType == 'image/png':
				fileExt = '.png'
			elif twilioContentType == 'image/jpeg':
				fileExt = '.jpg'
			else:
				print('Unrecognized mime type: %s' % twilioContentType)
				return

			# COPY THE FILE TO s3
			newFilename = tempFilename + fileExt
			newFileS3Key = S3_PREFIX + '/' + newFilename
			#print(newFileS3Key)

			bucket = s3.Bucket(S3_BUCKET) 
			bucket.upload_file(tempFilePath, newFileS3Key, ExtraArgs={'ACL':'public-read', 'ContentType':twilioContentType, 'Metadata':{'SenderNumber':senderNumber, 'ImgID':imgID}})
			print("Uploaded!")


			# CREATE THUMBNAIL VERSION
			print("Here 1")
			img_to_thumb = cv2.imread(tempFilePath,0)
			thumbnail_image = image_resize(img_to_thumb, THUMB_DIMENSION)
			thumbnail_image_gray = cv2.cvtColor(thumbnail_image, cv2.COLOR_BGR2GRAY)

			# SEND THUMB TO S3
			print("Here 2")
			thumb_str = cv2.imencode(fileExt, thumbnail_image_gray)[1].tostring()
			thumbnail_key =  S3_PREFIX + '/thumbs/' + newFilename
			object = s3.Object(S3_BUCKET, thumbnail_key)
			object.put(Body=thumbnail_image_gray, ACL='public-read', ContentType=twilioContentType)
			#s3.ObjectAcl(S3_BUCKET,thumbnail_key).put(ACL='public-read')
			print("Here 3")

		else:
			print("File not found")

	else:

		print('IrrelEvent')


def image_resize(image, max_dimension):

	# GET MAX OF H OR W AND SCALE THAT DOWN TO WORKING MAX
	(h, w) = image.shape[:2]

	# PORTRAIT
	if h >= w and h > max_dimension:
		reduction_ratio = h / max_dimension
		#print('PORTRAIT')

	# LANDSCAPE
	elif w >= h and w > max_dimension:
		reduction_ratio = w / max_dimension
		#print('LANDSCAPE')

	#print('RR: ', reduction_ratio)

	# NEW DIMENSIONS
	new_h = int(h / reduction_ratio)
	new_w = int(w / reduction_ratio)
	new_dims = (new_w, new_h)

	# GET RESIZED IMAGE
	new_img = cv2.resize(image, new_dims, interpolation = cv2.INTER_AREA)

	# RETURN RESIZED IMAGE
	return new_img

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