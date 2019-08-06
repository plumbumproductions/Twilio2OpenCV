import boto3
import json
import uuid
import urllib
import os
import regex

print("Cold Start")


# GLOBAL CONSTANTS
DDB = boto3.resource('dynamodb')
TABLE_USERS = os.environ['UsersTable']
TABLE_IMAGES = os.environ['ImagesTable']
FROM_NUM = ''

def lambda_handler(event, context):

	global FROM_NUM

	#print('Event: %s' % json.dumps(event))

	try:
		# GET BODY FROM EVENT
		this_body = urllib.parse.parse_qs(event['body'])

		# GET SENDER, MESSAGE, MEDIA URL FROM BODY
		FROM_NUM = str(this_body.get('From')[0])   # parse_qs() returns a DICT and the value part going along with each KEY is a LIST;  Also, from number looks like an int so cast it to string

		this_message_dict = this_body.get('Body')
		this_message = None
		if this_message_dict:
			this_message = this_message_dict[0]

		this_media_url_dict = this_body.get('MediaUrl0')
		this_media_url = None
		if this_media_url_dict:
			this_media_url = this_media_url_dict[0]

		# RETRIEVE USER BY FROM NUMBER
		if FROM_NUM:
			table = DDB.Table(TABLE_USERS)
			response = table.get_item(
				TableName = TABLE_USERS, 
				Key={
					'PhoneNo': FROM_NUM
				}
			)
		else:
			raise Exception('Missing From Number')

		# MAKE SURE WE FOUND A RECORD BY THAT FROM NUMBER
		if "Item" in response:
			UserRecord = response['Item']
		else:
			raise Exception('Unrecognized User: %s' % FROM_NUM)

		# HANDLE ANY FLAGS IN THE MESSAGE
		if this_message:
			m = regex.match('[A-z]-', this_message)
			if m:
				flag_handler(this_message)

		# HANDLE MEDIA URL
		# Images will not have a separate table in future versions.  Just trying to move things along here...
		if this_media_url:

			print('MEDIA URL: %s' % this_media_url)

			img_id = str(uuid.uuid4())

			table = DDB.Table(TABLE_IMAGES)
			response = table.put_item(
				Item={
					'ImgID': img_id,
					'url': this_media_url,
					'user': FROM_NUM
				}
			)

			print('PUT RESPONSE: %s' % response)

	except Exception as e:  
		print(e)

	finally:
		print("Finally")
		return {
			'statusCode': 200,
			'headers': { 'Content-Type': 'text/xml' },
			'body': '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
#			'body': '<?xml version="1.0" encoding="UTF-8"?><Response><Message><Body>Hello World!</Body></Message></Response>'
		}

def flag_handler(flag_to_parse):

	p = regex.compile('(?P<fflag>[A-z])-\s*(?P<fval>\w+)?')
	m = p.match(flag_to_parse)

	if m:
		flag = m.group('fflag')
		flag_value = m.group('fval')
		print('Flag: %s' % flag)
		print('Flag Val: %s' % flag_value)

		# Mode flag to chance which Rekognition function should be used to analyze the posted photos
		if flag.lower() == 'm':

			# object recognition
			if flag_value.lower() == 'o':
				update_account({'CurrentMode': flag_value.lower()})

			# person recognition
			elif flag_value.lower() == 'w':
				update_account({'CurrentMode': flag_value.lower()})

			# facial analysis
			elif flag_value.lower() == 'f':
				update_account({'CurrentMode': flag_value.lower()})

			# text recognition
			elif flag_value.lower() == 't':
				update_account({'CurrentMode': flag_value.lower()})

		# Add a new approved phone number/user
		elif flag.lower() == 'a':
			print('Account')

		# A cry for help
		elif flag.lower() == 'h':
			print('Help')

		else:
			print('UNRECOGNIZED FLAG: %s' % flag)
	

def update_account(UpdateDict):

	for key, value in UpdateDict.items():
		ue = "SET " + key + " = :v"
		eav = {':v': value}

	print('UpdateExpression: %s' % ue)
	print('ExpressionAttributeValues: %s' % eav)
	print('Number: %s' % FROM_NUM)
	print('Table: %s' % TABLE_USERS)

	if ue and eav and FROM_NUM:

		try:
			table = DDB.Table(TABLE_USERS)
			response = table.update_item(
				Key={'PhoneNo': FROM_NUM},
				UpdateExpression=ue,
				ExpressionAttributeValues=eav,
				ReturnValues="UPDATED_NEW"
			)

			print('UPDATE RESPONSE: %s' % response)
		
		except Exception as e:  
			print(e)  

	else:
		print('COULD NOT UPDATE')


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