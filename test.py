#!/usr/bin/env python3
import requests
import re

'''
x-byu-context: web$us
x-byutv-platformkey: xsaaw9c7y5
^ I dunno what these are for or if required

api.byutv.org/api3
    /page/getpage
        pageid
        channel=byutv
    
    pageid 56c21af3-61cc-4b15-b21c-ec68762fcfeb = magic number for main category listing
        - this came from the embedded json on the main index.html's link for "/programaz" which gives a UUID. and it was kinda hard to figure it out initially
    getpage for a show gives a list of seasonns (gives json with "type:'Show'")
    getpage for an episode just gives the title, nothing useful

    /list/getlistitems
        listid 
        start=0
        limit
        channel=byutv
    
    /catalog/getshow
        showid
        channel=byutv
        
        gives title/subtitle/description images, season count, episode count
    
    /catalog/getvideosforcontentv2
        contentid
        channel=byutv
        
        gives the URLs for streaming video content (hls, dash) and video length in hh:mm:ss
        
        hit the videoUrl or preplayUrl for DRM junk and it has a "playURL" which is the actual MPD
    
    /catalog/getepisode
        episodeid
        channel=byutv
        
        gives episode title/subtitle/description, airdate (startdate) length in hh:mm:ss and images
        alo gives showid and seasonid if you somehow got to this page without them?

images.byub.org (no thats not a typo)
    /uuid/size
    
    for example https://images.byub.org/30b20aca-1e11-4be0-a797-608545e6ea32/512x288
    but usually the json includes a complete URL so you probably don't need to formulate a request to this directly

'''

#allprog_re = re.compile(r'<h2\s[^>]*>([^<]{1,256})</h2[^>]*>\s*<div\s+[^>]*>\s*<a\s[^>]*href\s*=\s*"[^"]+\Wlistid=([A-Fa-f0-9-]{32,36})(?:\W[^"]+)?"[^>]*>\s*View All\s*</a', re.DOTALL)
#mainpage = requests.get('https://www.byutv.org/programaz').text
#for m in allprog_re.finditer(mainpage):
#    print(m.group(1), m.group(2))
