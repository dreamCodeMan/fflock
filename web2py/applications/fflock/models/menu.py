response.title = settings.title
response.subtitle = settings.subtitle
response.meta.author = '%(author)s <%(author_email)s>' % settings
response.meta.keywords = settings.keywords
response.meta.description = settings.description
response.menu = [
(T('Cluster Status'),URL('default','status')==URL(),URL('default','status'),[]),
(T('Jobs'),URL('default','jobs')==URL(),URL('default','jobs'),[]),
(T('Submit'),URL('default','submit')==URL(),URL('default','submit'),[]),
(T('Manage'),URL('default','manage')==URL(),URL('default','manage'),[]),
(T('Help'),URL('default','help')==URL(),URL('default','help'),[]),
]