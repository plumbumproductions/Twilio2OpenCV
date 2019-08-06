# Twilio2OpenCV

sam build --use-container

sam package --output-template-file packaged.yaml --s3-bucket plumbum-sam

sam deploy --template-file packaged.yaml --stack-name T2Ox --capabilities CAPABILITY_IAM

opt/event_triggers


