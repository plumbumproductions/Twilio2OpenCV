# TO DO

- CNAME for API endpoint URL (the one used by twilio)

- try a version that lets SAM create the ddb and s3 from scratch

- learn about prod and dev

- table structure, primary and sort keys, etc... Before t2ocv?

- build out missing functionality
	- Add user
	- Add face (w/name) to face index

- centralized config for things like name of face index, user database table, s3 folder for posted images

- can the triggers/events be more finely tuned?

- fix response to twilio in MsgFromTwilio.py

- Parameters (variables) in template
	- https://www.reddit.com/r/aws/comments/984v8x/simple_question_how_to_define_a_custom_variable/

- "Additionally I’m passing Twilio’s X-Twilio-Signature HTTP header through as “event.Signature” so you can properly validate the request as being from Twilio for full security."
	- http://dustinbolton.com/process-twilio-sms-text-message-in-nodejs-in-aws-lambda-function-via-api-gateway/