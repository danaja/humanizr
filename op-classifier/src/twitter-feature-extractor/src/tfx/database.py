import logging
import operator
import os
import json
import datetime
import smart_open

from tfx import errors


class Connection:
    def __init__(self, host, user, passwd, db):
        try:
            db = mysql.connect(host=host, user=user, passwd=passwd, db=db)
        except mysql.Error:
            raise errors.ConfFileError("Invalid MySQL connection details.")

        self.cursor = db.cursor()
        self.roost = False
        self.seeds = False

    def get_users_for_label(self, label):
        if label == -1:
            self.cursor.execute('SELECT distinct user_id FROM completed_seed_users')
            user_ids = [row[0] for row in self.cursor.fetchall()]
            print(len(user_ids))
            self.seeds = True
        elif label == -2:
            user_ids = []
            self.cursor.execute('SELECT distinct user_id FROM completed_seed_users')
            for profile in self.cursor.fetchall():
                self.cursor.execute('SELECT friend_id FROM friends WHERE user_id = %s', int(profile[0]))
                for friend in self.cursor.fetchall():
                    user_ids.append(int(friend[0]))
        else:
            self.roost = True
            self.cursor.execute("SELECT user_id FROM user_label_assignments "
                                        "WHERE label_id = %s", label)
            user_ids = [row[0] for row in self.cursor.fetchall()]
            return user_ids
    """
    def get_friends_for_user(self, user_id):
	if self.roost:      
		self.cursor.execute("SELECT json_list FROM friends "
		                    "WHERE user_id = %s "
		                    "ORDER BY view_timestamp DESC "
		                    "LIMIT 1", user_id)
		result = self.cursor.fetchall()
		
		try:
		    json_list = result[0][0]
		except IndexError:
		    log.warn("Missing entry in friends for %s" % user_id)
		    return []

		try:
		    friends_list = cjson.decode(json_list)
		except cjson.DecodeError:
		    log.warn("Invalid json_list in friends for %s" % user_id)
		    return []
	else:
		self.cursor.execute('SELECT friend_id FROM friends WHERE user_id = %s', user_id)
		result = self.cursor.fetchall()
		friends_list = []
		for friend in results:
			friends_list.append(friend)
    """
    def get_profile_for_user(self, user_id):
        if self.roost:
            self.cursor.execute("SELECT json_source FROM user_profiles "
                                "WHERE user_id = %s "
                                "ORDER BY view_timestamp DESC "
                                "LIMIT 1", user_id)
            result = self.cursor.fetchall()
        else:
            if self.seeds:
                print('seed')
                self.cursor.execute("SELECT json_source FROM seed_profiles "
                                        "WHERE user_id = %s ORDER BY dbid LIMIT 1", user_id)
                result = self.cursor.fetchall()
            else:
                self.cursor.execute("SELECT json_source FROM user_profiles "
                                "WHERE user_id = %s ORDER BY dbid LIMIT 1", user_id)
                result = self.cursor.fetchall()

            try:
                json_source = json.loads(result[0][0])
                return json_source
            except IndexError:
                logging.debug("No row in user_profiles for %s" % user_id)
            except ValueError:
                logging.debug("Invalid JSON in user_profiles for %s" % user_id)

            return {}

    def get_tweets_for_user(self, user_id):
	#changed by jamie, limited number of tweets used to test robustness
        self.cursor.execute("SELECT status_text, tweet_timestamp FROM user_tweets "
                            "WHERE user_id = %s limit 200", user_id)
        result = self.cursor.fetchall()
        return result

class TextFile:
    def __init__(self, tweet_dir, profile_file):
        """
        tweet_dir is the path to the directory where the tweet 
        files are stored. There should be one file per user 
        containing all his/her tweets. profile_file is the 
        path to the file containing all the json user info. 
        """

        # Path to directory of tweets
        self.tweetsd = tweet_dir

        # Indexed by label and then user id 
        self.profiles = {}

        # Initialize the profiles 
        num_wrong = 0
        with open(profile_file, 'r') as f:
            for index, line in enumerate(f):
                try:
                    if len(line.split("\t")) != 5:
                        num_wrong += 1
                        continue
                    user_id, username, json_source, timestamp, label = line.split("\t")
                    label = int(label.strip())
                    if label not in self.profiles:
                        self.profiles[label] = {}
                    self.profiles[label][user_id] = json_source
                except ValueError:
                    logging.warn("Invalid line profile information at line %d of %s" % (index, profile_file))
        
        print("NUM WRONG:", num_wrong, "out of", index)
        print(self.profiles.keys())

    def get_users_for_label(self, label):
        return self.profiles[label].keys()

    def get_profile_for_user(self, user_id):
        for label in self.profiles.keys():
            try:
                json_source = self.profiles[label][user_id]
                try:
                    return json.loads(json_source)
                except ValueError:
                    logging.warn("Invalid json profile for user %s" % user_id)
            except KeyError:
                continue

    def get_tweets_for_user(self, user_id):
        if self.tweetsd.endswith("/"):
            self.tweetsd = self.tweetsd[:-1]
        path = self.tweetsd + "/tweets-user-" + str(user_id) + ".txt"
        result = []
        with open(path, 'r') as f:
            for index, line in enumerate(f):
                try:
                    user_id, tweet_id, json_source, timestamp, tweet = line.split("\t")
                    d = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                    result.append((tweet, d))
                except ValueError:
                    continue
                    #logging.warn("Invalid line profile information at line %d of %s" % (index, path))
        return result

class JSONFiles:
    def __init__(self, tweet_dir):
        """
        tweet_dir is the path to the directory where the tweet 
        files are stored. There should be one JSON file per tweet
	    as outlined by Twitter's REST API.
        """

        # Path to directory of tweets
        if tweet_dir.endswith("/"):
                self.tweet_dir = tweet_dir[:-1]
        else:
            self.tweet_dir = tweet_dir
            # Indexed by label and then user id 
        self.profiles = {}

        # Indexed by user id
        self.tweets = {}

        json_files = os.listdir(tweet_dir)
        if len(json_files) < 1:
            logging.error('Empty tweet JSON directory.')
            exit()
        for f in json_files:
            with open("file.log", "a") as e_file:
                e_file.write(f) 
                e_file.write("\n")
            try:
                f = smart_open.open(tweet_dir + '/' + f, 'r')
                for line in f:
                    try:
                        try:
                            tweet_json = json.loads(line.strip())
                        except:
                            continue
                        try:
                            user_id = tweet_json['user']['id_str']
                        except KeyError as e:
                            user_id = str(tweet_json['user']['id'])
                        label = 0
                        if label not in self.profiles:
                            self.profiles[label] = {}
                        if user_id not in self.profiles[label]:
                            self.tweets[user_id] = []
                            self.profiles[label][user_id] = tweet_json['user']
                        temp_timestamps = tweet_json['created_at'].split(' ')
                        filtered_timestamps = []
                        for tt in temp_timestamps:
                            if '+' not in tt and '-' not in tt:
                                filtered_timestamps.append(tt)
                        timestamp = ' '.join(filtered_timestamps)
                        text = None
                        if 'text' in tweet_json:
                            text = tweet_json['text']
                        else:
                            text = ''
                        self.tweets[user_id].append((text, datetime.datetime.strptime(timestamp, "%a %b %d %H:%M:%S %Y")))
                    except:
                        with open("tweet.log", "a") as e_file:
                            e_file.write(line) 
            except ValueError as e:
                print(str(e))
                logging.warn("Invalid JSON file: %s" % f)

        max_count = 0
        for uid in self.tweets:
            if len(self.tweets[uid]) > max_count:
                max_count = len(self.tweets[uid])
        print('MAX NUMBER OF TWEETS FOR ONE USER: %d' % max_count)
        print('NUMBER OF USERS: %d' % len(self.tweets))

    def get_users_for_label(self, label):
        return self.profiles[label]

    def get_profile_for_user(self, user_id):
        for label in self.profiles.keys():
            try:
                json_source = self.profiles[label][user_id]
                try:
                    return json_source
                except ValueError:
                    logging.warn("Invalid json profile for user %s" % user_id)
            except KeyError:
                continue

    def get_tweets_for_user(self, user_id):
        try:
	        return self.tweets[user_id]
        except ValueError:
            pass
            #logging.warn("Invalid line profile information at line %d of %s" % (index, path))
        return result

