import os
import sys
import logging
import flickr_api as flickr

from configparser import ConfigParser
from argparse import ArgumentParser

LOGGER = 'flickr_folder_upload'


class FakeSecHead(object):
    def __init__(self, fp):
        self.fp = fp
        self.sechead = '[asection]\n'

    def readline(self):
        if self.sechead:
            try:
                return self.sechead
            finally:
                self.sechead = None
        else:
            return self.fp.readline()


def parse_config(cfg, opts):
    parser = ConfigParser()
    try:
        fp = open(os.path.expanduser(cfg), 'r')
    except Exception:
        print('Warning: can\'t open %s, using default values' % cfg)
        return
    parser.readfp(FakeSecHead(fp))
    fp.close()

    for section_name in parser.sections():
        for name, value in parser.items(section_name):
            if name not in opts:
                raise Exception(u'Invalid config file option \'%s\'' % name)
            opts[name] = value


def create_logger(log, verbose):
    FORMAT = '%(asctime)-15s %(message)s'
    console = log.strip() == '-'
    if console:
        logging.basicConfig(format=FORMAT)
    logger = logging.getLogger(LOGGER)
    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    if not console:
        fh = logging.FileHandler(log)
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter(FORMAT)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger


def add_to_photoset(photo_obj, photoset_title, photosets):
    """
    Adds a given photo to a given photoset
    """
    if photoset_title not in photosets.keys():
        new_photoset = flickr.Photoset.create(title=photoset_title, primary_photo=photo_obj)
        photosets[photoset_title] = new_photoset
    else:
        photosets[photoset_title].addPhoto(photo=photo_obj)


def flickr_auth():
    if os.path.exists('./.auth'):
        flickr.set_auth_handler(".auth")
    else:
        a = flickr.auth.AuthHandler()
        perms = "write"
        url = a.get_authorization_url(perms)
        print("Open this in a web browser -> ", url)
        oauth_verifier = input("Copy the oauth_verifier tag > ")
        a.set_verifier(oauth_verifier)
        flickr.set_auth_handler(a)
        a.save('.auth')


def upload_photos(upload_folder, max_retries):
    logger = logging.getLogger(LOGGER)
    user = flickr.test.login()
    logger.info("Logged in as %s", user.username)
    photosets = {p.title: p for p in user.getPhotosets()}

    if os.path.isdir(upload_folder):
        album_name = os.path.basename(upload_folder)
    else:
        logger.error("Must be run on a directory")
        sys.exit(1)

    # If we already have a photoset with this name, don't upload pictures we already have
    if album_name in photosets.keys():
        logger.info("Photoset %s already exists.  Getting contents so we can resume if needed.", album_name)
        remote_photos = {p.title: p for p in photosets[album_name].getPhotos()}
    else:
        logger.info("Photoset %s does not exist, so it will be created once the first photo is uploaded.", album_name)
        remote_photos = {}

    local_files = [f for f in os.listdir(upload_folder) if os.path.splitext(f)[1] in ('.jpg', '.png', '.gif')]

    logger.info("Processing %d files", len(local_files))

    retries = 0
    for count, filename in enumerate(local_files, start=1):
        if os.path.splitext(filename)[0] in remote_photos.keys():
            print("Skipping file %s because it has already been uploaded" % filename)
            continue
        logger.info("Starting upload of file %s", filename)
        while (retries <= max_retries) or (max_retries == -1):
            try:
                photo_obj = flickr.upload(photo_file=os.path.join(upload_folder, filename),
                                          is_public="0", is_friend="0", is_family="0", hidden="2", async="0")
                logger.info("Uploaded file %s", filename)
                add_to_photoset(photo_obj, album_name, photosets)
                logger.info("Added file %s to album %s", filename, album_name)
                break
            except Exception:
                logger.error("Failed to upload file %s")
                if (retries <= max_retries) or (max_retries == -1):
                    logger.error("Retrying...")
        logger.info("Progress: %d%% (%d/%d)", count / len(local_files) * 100, count, len(local_files))


def main():
    options = {'log': '-', 'config': '~/flickr_upload.conf',
               'retries': 10, 'folder': None, 'verbose': False}

    # First parse any command line arguments.
    parser = ArgumentParser(description='Upload photos to Flickr in a resumeable fashion')
    parser.add_argument('--retries', '-r', type=int, default=10, help='maximum number of retries (or -1 for unlimited)')
    parser.add_argument('--config', '-c', default="~/flickr_upload.conf", help='configuration file')
    parser.add_argument('--log', '-l', default="-", help='logfile (pass - for console)')
    parser.add_argument('folder', help='folder to upload to Flickr')
    parser.add_argument('--verbose', '-v', action='store_true', help='enable verbose logging')
    opts = parser.parse_args()

    # Parse configuration file.
    parse_config((opts.config and [opts.config] or [options['config']])[0], options)

    # Override parameters from config file with cmdline options.
    for a in options:
        v = getattr(opts, a)
        if v:
            options[a] = v

    logger = create_logger(options['log'], options['verbose'])
    logger.info(u'*** flickr_folder_upload starting up ***')

    flickr_auth()
    upload_photos(options['folder'], options['retries'])
    logger.info("Upload complete!")


if __name__ == '__main__':
    main()

#tickets = {}
#
#for filename in local_files:
#    if os.path.splitext(filename)[0] in remote_photos.keys():
#        print("Skipping file %s because it has already been uploaded" % filename)
#        continue
#    print("Starting upload of file %s" % filename)
#    ticket_obj = flickr.upload(photo_file=os.path.join(UPLOAD_FOLDER, filename),
#                               is_public="0", is_friend="0", is_family="0", hidden="2", async="1")
#    tickets[ticket_obj["id"]] = filename
#    print("Started upload of file %s" % filename)
#    print("Checking status of tickets")
#    statuses = flickr.Photo.checkUploadTickets(tickets.keys())
#    for status in statuses:
#        if status["complete"] == 1:
#            photo_obj = flickr.Photo(id=status["photoid"])
#            add_to_photoset(photo_obj, album_name)
#            print("Added file %s to album %s" % (tickets[status["id"]], album_name))
#            del tickets[status["id"]]
#
#print("Waiting for all uploads to finish")
#while len(tickets) > 0:
#    statuses = flickr.Photo.checkUploadTickets(tickets.keys())
#    for status in statuses:
#        if status["complete"] == 1:
#            photo_obj = flickr.Photo(id=status["photoid"])
#            add_to_photoset(photo_obj, album_name)
#            print("Added file %s to album %s" % (tickets[status["id"]], album_name))
#            del tickets[status["id"]]


