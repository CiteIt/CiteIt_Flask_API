import os
import aws_settings

VERSION_NUM = os.getenv('VERSION_NUM', '0.4')  # used to version the sha256 hash filename

AMAZON_ACCESS_KEY = 'AKIAXHQAFKHENPCJIMOI'     # 'ABCDEFGH123456789'
AMAZON_SECRET_KEY = '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'     # 'alksdfj;2452lkjr;ajtsaljgfslakjfgassgf'
AMAZON_S3_BUCKET = 'read.citeit.net'       # 'read.citeit.net'
AMAZON_S3_ENDPOINT = 's3.amazonaws.com'   # 's3.amazonaws.com'
AMAZON_REGION_NAME = 'us-east-1'           # 'us-east-1'

SAVE_DOWNLOADS_TO_FILE = False

JSON_FILE_PATH = '/tmp/'   # in Lambda, you need to save to /tmp folder
SQLALCHEMY_DATABASE_URI = 'postgresql://username:password@localhost/database_name'

# Number of URL lookups to make simulaneously:
# pool = Pool(processes=settings.NUM_DOWNLOAD_PROCESSES)
NUM_DOWNLOAD_PROCESSES = 5

# Remove the following Unicode code points from Hash
URL_ESCAPE_CODE_POINTS = set ([
    10, 20, 160
])

# Remove the following Unicode code points from Hash
TEXT_ESCAPE_CODE_POINTS = set ( [
    2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18
    , 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 39
    , 96, 160, 173, 699, 700, 701, 702, 703, 712, 713, 714, 715, 716
    , 717, 718, 719, 732, 733, 750, 757, 8211, 8212, 8213, 8216, 8217
    , 8219, 8220, 8221, 8226, 8203, 8204, 8205, 65279, 8232, 8233, 133
    , 5760, 6158, 8192, 8193, 8194, 8195, 8196, 8197, 8198, 8199, 8200
    , 8201, 8202, 8239, 8287, 8288, 12288
])


