from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey, Text, create_engine, Boolean
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import relation, backref

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

photo_tags = Table('photo_tags', Base.metadata,
    Column('photo_id', Integer, ForeignKey('photos.id')),
    Column('tags_id', Integer, ForeignKey('tags.id'))
)

photo_albums = Table('photo_albums', Base.metadata,
    Column('photo_id', Integer, ForeignKey('photos.id')),
    Column('albums_id', Integer, ForeignKey('albums.id'))
)

fb_albums = Table('fb_albums', Base.metadata,
   Column('album_id', Integer, ForeignKey('albums.id')),
   Column('fb_album_id', Integer, ForeignKey('fbalbum.id'))
)

class FBAlbum(Base):
    __tablename__ = 'fbalbum'
    id = Column(Integer, primary_key=True)
    facebook_id = Column(Integer)
    albums = relation('Album', secondary=fb_albums, backref='fb_albums') 
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

class Album(Base):  
    __tablename__ = 'albums'
    
    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(Text)
    flickr_id = Column(Integer)
    facebook_id = Column(Integer)
    flickr_photo_count = Column(Integer)
    facebook_photo_count = Column(Integer)
    dirty = Column(Boolean)

    def __str__(self):
        return "Album: %s (Flickr %s, Facebook %s)" % (self.title, self.flickr_id, self.facebook_id)
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

class Photo(Base):
    __tablename__ = 'photos'
    id = Column(Integer, primary_key=True)
    title = Column(String)
    url = Column(String)
    description = Column(Text)
    flickr_id = Column(Integer)
    facebook_id = Column(Integer)
    private = Column(Boolean)
    dirty = Column(Boolean)
    tags = relation('Tag', secondary=photo_tags, backref='photos')   
    albums = relation('Album', secondary=photo_albums, backref='photos') 

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __str__(self):
        return "Photo: %s (Flickr %s, Facebook %s)" % (self.title, self.flickr_id, self.facebook_id)

class Tag(Base):
    __tablename__ = 'tags'
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    id = Column(Integer, primary_key=True)
    text = Column(String)
    clean_text = Column(String)

engine = create_engine('sqlite:///./photos.db', echo=False)

Base.metadata.create_all(engine) 

Session = sessionmaker(bind=engine)
session = Session()
