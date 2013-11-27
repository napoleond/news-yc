import os
from xml.dom.minidom import parseString
from datetime import datetime

import webapp2, jinja2

from google.appengine.api.urlfetch import fetch
from google.appengine.api import memcache

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

fp_template = JINJA_ENVIRONMENT.get_template('fp.html')

def pluck(xml,tag):
    try:
        return xml.getElementsByTagName(tag)[0].firstChild.data
    except:
        return None

class MainPage(webapp2.RequestHandler):

    def get(self):
        frontpage = memcache.get('frontpage')
        if frontpage is None:
            fp_req = fetch('https://www.hnsearch.com/bigrss')
            fp_xml = parseString(fp_req.content)

            #parse out an array of story dicts
            fp_items = []
            fp_5 = []
            items_xml = fp_xml.getElementsByTagName('item')
            for i,item_xml in enumerate(items_xml):
                #fields:
                # title, link, comments,hnsearch_id,username,create_ts
                # num_comments, points, description, guid
                item = {
                    "title": pluck(item_xml,"title"),
                    "link": pluck(item_xml,"link"),
                    "comments": pluck(item_xml,"comments"),
                    "id": pluck(item_xml,"hnsearch_id"),
                    "username": pluck(item_xml,"username"),
                    "create_ts": pluck(item_xml,"create_ts"),
                    "num_comments": pluck(item_xml,"num_comments"),
                    "points": pluck(item_xml,"points")
                }
                if item['create_ts'] is not None:
                    #look here for explanation of ranking:
                    #http://www.righto.com/2013/11/how-hacker-news-ranking-really-works.html
                    delta = datetime.utcnow() - datetime.strptime(item['create_ts'],"%Y-%m-%dT%H:%M:%SZ")
                    hours_ago = delta.total_seconds() / 3600
                    item['raw_score'] = (float(item['points'])-1.0) ** 0.8 / (float(hours_ago)+2.0) ** 1.8

                    if i < 3:
                        fp_items.append(item)
                    elif i == 3:
                        #calculate prev_score and then penalty for all 5
                        fp_items.append(item)
                        fp_5 = [x['raw_score'] for x in fp_items]
                        prev_score = sum(fp_5)/float(len(fp_5))
                        for k in fp_items:
                            k['penalty'] = 1.0
                    else:
                        prev_score = sum(fp_5)/float(len(fp_5))
                        if item['raw_score'] > prev_score:
                            item['penalty'] = prev_score / item['raw_score']
                        else:
                            item['penalty'] = 1.0
                            fp_5.pop(0)
                            fp_5.append(item['raw_score'])
                            prev_score = sum(fp_5)/float(len(fp_5))
                        fp_items.append(item)
            #use points and create_ts to determine ranking
            fp_items.sort(key=lambda x: -x['raw_score'])
            #pass to jinja template
            frontpage = fp_template.render({"items":fp_items})
            #cache result
            if not memcache.add('frontpage',frontpage,60):
                logging.error('Memcache set failed')
        self.response.write(frontpage)


application = webapp2.WSGIApplication([
    ('/', MainPage),
], debug=True)

