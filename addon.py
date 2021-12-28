#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import re
import requests
import json
from urllib.parse import parse_qsl, quote_plus

import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin

API_BASE = 'https://api.byutv.org/api3'
API_HEADERS = {
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:95.0) Gecko/20100101 Firefox/95.0',
    'x-byutv-context':'web$us',
    'x-byutv-platformkey':'xsaaw9c7y5',
    #'Referer':'https://www.byutv.org/',
    #'Origin':'https://www.byutv.org',
    #'Sec-Fetch-Mode':'cors',
    #'Sec-Fetch-Dest':'empty',
	#'Sec-Fetch-Site':'same-site',
}

def log(txt, *args, level=xbmc.LOGINFO):
    xbmc.log('byu-tv : ' + txt.format(*args), level=level)

def get_json(url, **params):
    if 'channel' not in params:
        params['channel'] = 'byutv'
    resp = requests.get(API_BASE + url, params=params, headers=API_HEADERS)
    if resp.status_code != 200:
        log('GET {} failed: code {}', url, resp.status_code)
        return {}
    else:
        return resp.json()

def do_login(email, pw):
    info = {'email':email,'password':pw}
    resp = requests.post('https://accounts-api.byub.org/v1/public/login', json=info, headers=API_HEADERS)
    # TODO save tokens
    auth = resp.json()
    API_HEADERS['Authorization'] = auth['access_token']
    token_expr = auth['expiration'] - 60 + time.time()
    refresh_token = auth['refresh_token']

# auth required for these:
# TODO favorites? /user/isfavorited?contentid=<UUID>
#           POST /user/addtofavorites {"contentid":uuid}
#     ... looks like getting the favorites list is based on the user from GET https://accounts-api.byub.org/v1/public/users/me?channel=byutv
# TODO percent played: /user/getpercentplayedforepisodes?episodelist=[%276da07694-9548-4225-94af-95f24df89817%27,%27dd6bbd6e-1bb3-4950-95e1-2f5ef931a1f7%27,%27724cc8aa-52c6-42a4-9e4d-ef33674d4824%27,%2709ad97da-c4a8-44c4-91c7-18635bee713e%27,%2768aaf2f3-e61e-438f-8495-e71711293350%27,%2748bb00af-5cfc-4231-8ea6-21c91f7dc2eb%27,%2720e3d42b-38c9-4ef9-8323-4199763907aa%27,%27e2e5de1a-f9b2-4c33-842f-cec2c157c7de%27,%272e69312c-aa09-4ee4-97e7-355f18a3d837%27,%272cc09765-6a1b-4360-b4ce-d802d1fc6de9%27,%274fbec4d3-6c77-4f3d-bed0-f41a923caec1%27,%27b8773ebd-bfaf-4642-9353-cffac5b4f470%27,%2779e16163-7385-4082-ae3c-81851864af32%27,%27abdae8e9-e3cf-4bdd-83e4-aed423652025%27,%2792cd1a13-3213-4638-92e3-238a73438aad%27,%27539b7898-7bcf-4d3c-b249-8a3f0fe9104a%27,%270032042b-55e6-4014-9a99-4d29ad4e66ac%27,%279a75db84-a8a0-4bf4-8b39-26964f25cb98%27]&channel=byutv'
# also be a good citizen and check requireLogin on episodes

def list_categories():
    items = []
    # pageid 56c21af3-61cc-4b15-b21c-ec68762fcfeb = magic number for main category listing
    resp = get_json('/page/getpage', pageid='56c21af3-61cc-4b15-b21c-ec68762fcfeb')
    for cat in resp.get('lists', []):
        if cat.get('contentType', '') != 'Show':
            continue
        id = cat.get('id', '')
        if not id:
            continue
        item = xbmcgui.ListItem(label=cat['name'])
        item.setInfo('video', {'title':cat['name'], 'set':cat['name'], 'genre':cat['name'].split()})
        url = '{0}?action=category&id={1}'.format(PLUGIN_BASE, id)
        items.append((url, item, True))
    log('Listed {} categories', len(items))
    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_GENRE)
    xbmcplugin.endOfDirectory(HANDLE)

def getart(img, poster=False):
    art = {}
    if img and 'images' in img[0] and img[0]['images'] and 'url' in img[0]['images'][0]:
        for i in img[0]['images']:
            if 'size' in i:
                if poster and (i['size'].startswith('1280') or i['size'].startswith('720')):
                    art['poster'] = i['url']
                    poster = False
                if i['size'].startswith('512'):
                    art['thumb'] = i['url']
                elif i['size'].startswith('128x'):
                    art['icon'] = i['url']
    return art

def list_category(listid):
    items = []
    # start and limit are required, webapp uses 0,20
    # response has a "hasMore" key (boolean value) to indicate items over the limit
    resp = get_json('/list/getlistitems', listid=listid, start=0, limit=100)
    for show in resp.get('items', []):
        if show.get('type', '') != 'Show':
            continue

        target = show.get('target', {})
        id = target.get('value', None)
        if not id:
            id = show.get('id', '')
            if not id:
                continue
        
        if target.get('type', '') == 'Player':
            item = xbmcgui.ListItem(label=show['title'])
            item.setArt(getart(show.get('images', [])))
            item.setInfo('video', {
                'title':show.get('subtitle', show['title']),
                'tvshowtitle':show['title'],
                'plot':show.get('description', ''),
                'mediatype':'video'
            })
            item.setProperty('IsPlayable', 'true')
            url = '{0}?action=play&id={1}'.format(PLUGIN_BASE, id)
            items.append((url, item, False))
        else:
            item = xbmcgui.ListItem(label=show['title'])
            if show.get('subtitle', ''):
                item.setLabel2(show['subtitle'])
            art = getart(show.get('images', []), poster=True)
            item.setArt(art)
            item.setInfo('video', {
                'title':show['title'],
                'set':show['title'],
                'setoverview':show.get('description', ''),
                'mediatype':'tvshow'
            })
            url = '{0}?action=show&id={1}&poster={2}'.format(PLUGIN_BASE, id, quote_plus(art.get('poster', '')))
            items.append((url, item, True))
    
    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(HANDLE)

def list_show(showid, poster=''):
    # catalog/getshow?showid=<UUID> gives title/subtitle/description images, season count, episode count
    # ... but does not give the season list with season IDs
    items = []
    eps = []
    n = 0
    resp = get_json('/page/getpage', pageid=showid)
    for season in resp.get('lists', []):
        if season.get('type', '') != 'ShowSeason':
            if season.get('contentType', '') == 'Episode':
                eps.append(season.get('id', ''))
            continue
        n += 1
        id = season.get('id', '')
        if not id:
            continue
        
        item = xbmcgui.ListItem(label=season['name'])
        item.setInfo('video', {
            'title':season['name'], 
            'set':season['name'], 
            'setoverview':season['name'], 
            'season':n, 
            'mediatype':'season'
        })

        if poster:
            item.setArt({'poster':poster})

        snum = n
        try:
            if season['name'].startswith('Season'):
                snum = int(season['name'][6:].strip())
        except:
            pass

        url = f'{PLUGIN_BASE}?action=season&n={snum:03d}&id={id}'
        items.append((url, item, True))
    
    xbmcplugin.addDirectoryItems(HANDLE, sorted(items, key=lambda t: t[0]), len(items))
    
    # show has un-season'd episodes, list them too
    for e in eps:
        if e:
            ei = list_season(e, 0, True)
            xbmcplugin.addDirectoryItems(HANDLE, ei, len(ei))

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE)
    xbmcplugin.endOfDirectory(HANDLE)

def list_season(sid, snum, listonly=False):
    n = 0
    items = []

    # getpage for an episode just gives the title, nothing useful
    # start and limit are required, webapp uses 0,20
    # response has a "hasMore" key (boolean value) to indicate items over the limit
    resp = get_json('/list/getlistitems', listid=sid, start=0, limit=50)
    for ep in resp.get('items', []):
        if ep.get('type', '') != 'Episode':
            continue
    
        n += 1

        id = ep.get('target', {}).get('value', None)
        if not id:
            id = ep.get('id', '')
            if not id:
                continue
        
        url = '{0}?action=play&id={1}'.format(PLUGIN_BASE, id)
        
        info = {
            'tvshowtitle':ep['title'],
            'plot':ep.get('description', '')
        }

        if 'subtitle' in ep:
            info['title'] = ep['subtitle']
        else:
            info['title'] = ep['title']
        
        item = xbmcgui.ListItem(label=info['title'])
        item.setArt(getart(ep.get('images', [])))
        
        if 'videoLength' in ep:
            dur = 0
            p = ep['videoLength'].split(':', 2)
            if len(p) >= 3:
                dur = int(p[0]) * 3600
                del p[0]
            if len(p) > 1:
                dur += int(p[0]) * 60
                del p[0]
            if len(p):
                dur += int(p[0])
            if dur:
                info['duration'] = dur
        if snum:
            info['mediatype'] = 'episode'
            info['season'] = snum
            info['episode'] = n
        else:
            info['mediatype'] = 'video'
            
        # TODO: check this
        #if ep.get('requireLogin', False):
        #    url = ''
        #    info['overlay'] = 3 #locked
        
        item.setInfo('video', info)
        item.setProperty('IsPlayable', 'true')
        items.append((url, item, False))
    
    if listonly:
        return items
    
    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_EPISODE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
    xbmcplugin.endOfDirectory(HANDLE)

def play_video(vid):
    # TODO post /user/saveplayhistory {'id':uuid,'playhead':seconds}
    vr = get_json('/catalog/getvideosforcontentv2', contentid=vid)
    if 'videos' in vr:
        vr = vr['videos']
        if 'dash1' in vr:
            vr = vr['dash1']
        elif 'dash' in vr:
            vr = vr['dash']
        else:
            log('No DASH section found in getvideosforcontentv2')
    
    if 'videoUrl' in vr:
        url = vr['videoUrl']
    else:
        log('No videoUrl :(')
        url = ''

    if url:
        mpdresp = requests.get(url, headers=API_HEADERS)
        m = re.search(r'"([^"]*/wv\?[^"]*)"', mpdresp.text)
        lic = m.group(1).replace('&amp;', '&')
        lic += '||R{SSM}|'

        item = xbmcgui.ListItem(path=url, offscreen=True)
        item.setProperty('inputstream','inputstream.adaptive')
        item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
        item.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
        item.setProperty('inputstream.adaptive.license_key', lic)
        item.setMimeType('application/dash+xml')
        item.setProperty('IsPlayable', 'true')
        xbmcplugin.setResolvedUrl(HANDLE, True, item)
    else:
        log('No video URL? vid={}, resp={}', vid, vr, level=xbmc.LOGERROR)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem(path='', offscreen=True))

if __name__ == '__main__':
    PLUGIN_BASE = sys.argv[0]
    HANDLE = int(sys.argv[1])

    if len(sys.argv) > 2 and len(sys.argv[2]) > 1:
        args = dict(parse_qsl(sys.argv[2][1:]))
    else:
        args = {}
    
    action = args.get('action', None)
    if not action:
        list_categories()
    elif action == 'category':
        list_category(args.get('id'))
    elif action == 'show':
        list_show(args.get('id'), args.get('poster', ''))
    elif action == 'season':
        list_season(args.get('id'), int(args.get('n', 0)))
    elif action == 'play':
        play_video(args.get('id'))
    else:
        log('Unknown action in params: {}', args, level=xbmc.LOGERROR)
