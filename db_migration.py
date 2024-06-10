import json 

async def setup(bot):
    db = bot.db 
    
    #autoresponders 
    old_ars = await db.fetch('select * from ars')
    for ar in old_ars:
        phrase = ar['phrase']
        data = json.loads(ar['data'])
        detection = data['detection']
        
        detection_map = {
            'full': 'matches',
            'any': 'contains',
            'regex': 'regex',
            'beginning': 'starts',
            'word': 'contains_word'
        }
        # if data.get('text', 0) == 0:
        #     print(phrase)
        #     continue
        # if data.get('embed', 0) == 0:
        #     print(embed)
        #     continue

        if 'autoemojis' in data:
            actions = json.dumps(
                [
                    {
                        'type': 'add_reactions',
                        'kwargs': {
                            'emojis': data['autoemojis']
                        }
                    }
                ],
                indent=4
            )
        else:   
            actions = [   
                    {
                        'type': 'send_message',
                        'kwargs': {
                            'is_dm': False,
                            'channel': None,
                            'layout': {
                                'name': None,
                                'content': data.get('text'),
                                'embeds': [data['embed']] if data['embed'] else [],
                                'delete_after': data.get('delete_response_after'),
                                'reply': False,
                                'mention_author': None
                            }
                        }
                    }
                ] 
            
            if data.get('delete_trigger'):
                actions.append(
                    {
                        'type': 'delete_trigger_message',
                        'kwargs': {}
                    }
                )   
            
            if data.get('give_roles'):
                actions.append(
                    {
                        'type': 'add_roles',
                        'kwargs': {
                            'roles': data['give_roles']
                        }
                    }
                )

            if data.get('remove_roles'):
                actions.append(
                    {
                        'type': 'remove_roles',
                        'kwargs': {
                            'roles': data['remove_roles']
                        }
                    }
                )

            actions = json.dumps(actions, indent=4)
        restrictions = {}
        for key in ['wlusers', 'blusers', 'wlchannels', 'blchannels', 'wlroles', 'blroles']:
            if key in data:
                newkey = key.replace('wl', 'whitelisted_').replace('bl', 'blacklisted_') 
                restrictions[newkey] = data[key]
        
        cooldown = None
        for key in ['user', 'channel', 'guild']:
            if key+'_cooldown' in data:
                if key == 'guild':
                    newkey = 'global'
                else:
                    newkey = key
                cooldown = {}
                cooldown['bucket_type'] = newkey
                cooldown['rate'] = data[key+'_cooldown']
                cooldown['per'] = 1
                cooldown = json.dumps(cooldown, indent=4)

        query = '''INSERT INTO auto_responders (
                       name,
                       trigger, 
                       detection, 
                       actions,
                       restrictions, 
                       cooldown,
                       author_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7) 
                '''
        

        await db.execute(query, phrase, phrase, detection_map[detection], actions, json.dumps(restrictions, indent=4), cooldown, 496225545529327616)


    return
    # code responders
    names = set()
    old_crs = await db.fetch('select * from crs')
    for cr in old_crs:
        phrase = cr['name']
        data = json.loads(cr['options'])
        detection = data['detection']
        
        detection_map = {
            'full': 'matches',
            'any': 'contains',
            'regex': 'regex',
            'beginning': 'starts',
            'word': 'contains_word'
        }
        
        cooldown = None
        for key in ['user', 'channel', 'guild']:
            if key+'_cooldown' in data:
                if key == 'guild':
                    newkey = 'global'
                else:
                    newkey = key
                cooldown = {}
                cooldown['bucket_type'] = newkey
                cooldown['rate'] = data[key+'_cooldown']
                cooldown['per'] = 1
                cooldown = json.dumps(cooldown, indent=4)

        query = '''INSERT INTO code_responders (
                    name,
                    trigger, 
                    detection, 
                    code,
                    cooldown,
                    author_id
                ) VALUES ($1, $2, $3, $4, $5, $6) 
            '''

        await db.execute(query, phrase, phrase, detection_map[detection], cr['code'], cooldown, 496225545529327616)

    # sticky messages   

    old_sms = await db.fetch('select * from stickymessages')   
    for sm in old_sms:
        channel = bot.get_channel(sm['channel_id'])
        text = sm['text']
        embed = sm['embed']
        layout = {
            'name': None,
            'content': text,
            'embeds': [embed] if embed else []
        }
        last_message_id = sm['last_msg_id']
        query = '''INSERT INTO sticky_messages (
                    channel_id,
                    layout,
                    last_message_id
                ) VALUES ($1, $2, $3)
                ON CONFLICT (channel_id)
                DO NOTHING
            '''
        await db.execute(query, channel.id, json.dumps(layout, indent=4), last_message_id)
    
# async def setup(bot):
#     rows = await bot.db.fetch('select * from auto_responders')
#     for row in rows:
#         a = json.loads(row['actions'])[0]
#         if a['type'] == 'send_message':
#             a['kwargs']['channel'] = 'this'
#         query = '''UPDATE auto_responders
#                    SET actions = $1
#                    WHERE name = $2
#                 '''
#         await bot.db.execute(query, json.dumps([a], indent=4), row['name'])

# async def setup(bot):
#     # copy to auto_responders
#     # await bot.db.execute('create table new_auto_responders as select * from auto_responders')
#     # await bot.db.execute('delete from new_auto_responders')
#     ars = await bot.db.fetch('select * from auto_responders')

#     for ar in ars:
#         actions = json.loads(ar['actions'])
#         newactions = []
#         for action in actions:
#             kwargs = action.copy()
#             kwargs.pop('type')

#             # remove every key besides type in the original 

#             newactions.append({
#                 'type': action['type'],
#                 'kwargs': kwargs
#             })
#             #insert into new 
#         await bot.db.execute('''INSERT INTO new_auto_responders (
#             name,
#             trigger,
#             detection,
#             actions,
#             restrictions,
#             cooldown,
#             author_id
#         ) VALUES ($1, $2, $3, $4, $5, $6, $7)''', ar['name'], ar['trigger'], ar['detection'], json.dumps(newactions,indent=4), ar['restrictions'], ar['cooldown'], ar['author_id'])
#         print('done with',ar['name'] )


     

