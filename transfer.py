from model import session, Photo, Album, Tag, FBAlbum
import time
#p = Photo(flickr_id=1, facebook_id=2, title="foo", description="bar")
#session.add(p)
#p.albums.append(Album(description="album"))
#session.commit()

api_key = '065ba003282b719d84e2a322046c7364'
secret = 'a192dec51fb99499'

import json as simplejson
import flickrapi

def setup_flickr():

    flickr = flickrapi.FlickrAPI(api_key, secret, format='json') 
    (token, frob) = flickr.get_token_part_one(perms='write')
    print flickr.auth_url(perms='write', frob=frob)
    if not token: raw_input("Press ENTER after you authorized this program")
    flickr.get_token_part_two((token, frob))
    return flickr

def sync_local_sets(flickr):
    
    sets = simplejson.loads(flickr.photosets_getList(nojsoncallback=1))
    
    for set in sets['photosets']['photoset']:
        (id, title, description, count) =  (int(set['id']), set['title']['_content'], set['description']['_content'], int(set['photos'])) 
        result = session.query(Album).filter(Album.flickr_id == id).first()
        if result:
            if result.title != title or result.description != description or result.flickr_photo_count != count:
                result.title = title
                result.description = description
                result.flickr_photo_count = count
                result.dirty = True
                print "Updating %s" % result.id
        else:
            a = Album(flickr_id = id, title=title, description=description, flickr_photo_count=count, dirty=False)
            session.add(a)
        session.commit()    

def sync_photoset_photos(id, flickr):
    album = session.query(Album).filter(Album.flickr_id == id).first()
    if not album:
        print "Call sync_local_sets first."
        return
    page = 0
    print "Syncing album %s..." % id
    while page < 1 or page < int(photos['photoset']['pages']):
        page += 1
        photos = simplejson.loads(flickr.photosets_getPhotos(photoset_id=id, nojsoncallback=1, page=page, per_page=250))
        for photo in photos['photoset']['photo']:
            p = sync_photo(photo['id'], flickr)
            album.photos.append(p)
            time.sleep(0.1)
    

    session.commit()

def loc_to_string(p):
    
    if p.has_key('location'):
        loc = p['location']
    else:
        return "unknown"
    out = []
    for key in ('neighborhood','locality', 'county', 'region', 'country'):
        if loc.has_key(key):
            out.append(loc[key]['_content'])
    return ", ".join(out)    

def url_for_photo(p):
    return 'http://farm%s.static.flickr.com/%s/%s_%s.jpg' % (p['farm'], p['server'], p['id'], p['secret'])

def sync_tags(db_photo, photo):
    for t in photo['tags']['tag']:
        tag = session.query(Tag).filter(Tag.text == t['raw']).first()
        if not tag:
            tag = Tag(clean_text=t['_content'], text=t['raw'])
        db_photo.tags.append(tag)
    return db_photo    

def sync_photo(id, flickr, check_dirty=False):    
    print id
    db_photo = session.query(Photo).filter(Photo.flickr_id == id).first()
    if db_photo and not check_dirty:
        print 'Photo is already local.'
        return db_photo
    photo = simplejson.loads(flickr.photos_getInfo(photo_id=id, nojsoncallback=1))
    p = photo['photo'] 
    (id, title) = (int(p['id']), p['title']['_content'])
    url = url_for_photo(p)
    page_url = p['urls']['url'][0]['_content']
    description = """%s\n
%s
Taken: %s in %s
Flickr: %s""" % (p['title']['_content'], p['description']['_content'], p['dates']['taken'], loc_to_string(p), page_url)

    if db_photo:
        print "Photo %s already exists" % id
        if db_photo.title == title and db_photo.description == description:
           return db_photo 
        db_photo.dirty = True   
        db_photo.title = title
        db_photo.description = description
    else:    
        url = url_for_photo(p)
        db_photo = Photo(title= title, description=description, flickr_id=id, dirty=False, url=url) 
        if not p['visibility']['ispublic']:
            db_photo.private = True
        session.add(db_photo)
    sync_tags(db_photo, p)
      
    session.commit()

    return db_photo

def setup_facebook():

    FB_SETTINGS = '.facebook'
    from facebook import Facebook

    # Get api_key and secret_key from a file
    fbs = open(FB_SETTINGS).readlines()
    facebook = Facebook(fbs[0].strip(), fbs[1].strip())
    facebook.auth.createToken()
    print facebook.get_login_url()
    #facebook.session_key = "1b2fcc7cabfc2574898155c2-1926269"
    #facebook.secret = u'd21ee6b6b24515fb00af58fa3bfea907'
    raw_input("waiting")
    facebook.auth.getSession()    
    return facebook

def create_secondary_facebook_album(set, facebook):
    title = "%s (#%s)" % (set.title, len(set.fb_albums) + 2) 
    print "Created %s" % title
    data = facebook.photos.createAlbum(name=title, description=set.description, visible="everyone")
    set.fb_albums.append(FBAlbum(facebook_id=int(data['aid'])))
    session.commit()
    return int(data['aid'])

def create_facebook_album(set, facebook):
    
    data = facebook.photos.createAlbum(name=set.title, description=set.description, visible="everyone")
    set.facebook_id = data['aid']
    session.commit()
    

def copy_photo_to_facebook_album(photo, set, facebook, tag_map = None):
    if photo.facebook_id:
        return 0
    if photo.private:
        return 0
    f = open("/tmp/fb_photo.jpg", "w")
    import urllib
    u = urllib.urlopen(photo.url)
    f.write(u.read())
    f.close()

    aid = 0
    if len(set.fb_albums) == 0:
        aid = set.facebook_id
    else:
        aid = set.fb_albums[-1].facebook_id
    a = facebook.photos.getAlbums(aids=[aid])
    count = a[0]['size']
    if count >= 60:
        aid = create_secondary_facebook_album(set, facebook)

    tag_text = ', '.join(map(lambda x: x.text, photo.tags))
    description = "%s\nTags: %s" % (photo.description, tag_text)
    data = facebook.photos.upload(image="/tmp/fb_photo.jpg", aid=aid, caption=description)
    photo.facebook_id = int(data['pid'])
    session.commit()
    if tag_map:
        seen = []
        for t in photo.tags:
            if t.text in tag_map:
                try:
                    if not tag_map[t.text] in seen:
                        facebook.photos.addTag(pid=photo.facebook_id, tag_uid=tag_map[t.text])
                        seen.append(tag_map[t.text])

                except:
                    facebook.photos.addTag(pid=photo.facebook_id, tag_text=t.text)
            
    print "Copied %s to %s" % (photo.flickr_id, photo.facebook_id)
    return 1

def setup_namemap():
    f = open("name-map.txt")
    names = {}
    for line in f:
        key, value = line.strip().split(": ")
        names[key] = value
    return names    

def copy_album_to_facebook(set):
    if len(set.photos) == 0:
        print "sync photoset photos first."
        return
    if not len(filter(lambda x: x.private != True, set.photos)):
        print "All photos in this set are private"
        return
    if set.facebook_id and set.facebook_id==-1:
        print "Facebook ID is -1: skipping this album."
        return
    count =  len(filter(lambda x: not x.facebook_id, set.photos))
    if count > 200:
        print "Too many pictures in set %s: %s" % (set.flickr_id, count)
        return
    facebook = setup_facebook()
    name_map = setup_namemap() 
    if not set.facebook_id:
        print "No facebook ID yet, creating"
        create_facebook_album(set, facebook)
    copied = 0
    for photo in set.photos:
        try:
            copied += copy_photo_to_facebook_album(photo, set, facebook, tag_map = name_map)
        except KeyboardInterrupt, E:
            raise E
        except Exception, E:
            print "Error on %s: %s. Skipping rest of album." % (photo.flickr_id, E)
            break 
     
    print "Copied %s" % copied

f = setup_flickr()
sync_local_sets(f)
sets = session.query(Album).filter(Album.flickr_id==72157628267826521)

for set in sets:
    if set.flickr_photo_count != len(set.photos):
        sync_photoset_photos(set.flickr_id, f)
        print "Synced %s" % set.flickr_id
    #    time.sleep(5)

    copy_album_to_facebook(set) 
