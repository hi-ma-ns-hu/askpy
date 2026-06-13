import json

from shared.storage.redis import redis


MAX_RECENT_MSGS = 5
TTL = 60 * 60 * 24  # 24 HRS

async def get_conversation_context(workspace_id: str, thread_id: str) -> list[dict]:
  r_key = f'ctx:{workspace_id}:{thread_id}'

  first_message = await redis.get(f'{r_key}:first')
  recent_messages = await redis.lrange(f'{r_key}:recent', -MAX_RECENT_MSGS*2, -1)

  messages = list()

  rm = [json.loads(m) for m in recent_messages]

  # if first_message is already in recent_messages, don't include it again
  if first_message:
    fm = json.loads(first_message)
    if fm not in rm:
      messages.append(fm)

  messages.extend(rm)

  return messages


async def save_conversation_context(workspace_id: str, thread_id: str, question: str, answer: str):
  r_key = f'ctx:{workspace_id}:{thread_id}'

  first_message = await redis.get(f'{r_key}:first')
  if not first_message:
    await redis.set(f'{r_key}:first', json.dumps({'role': 'user', 'content': question}))

  await redis.rpush(f'{r_key}:recent', json.dumps({'role': 'user', 'content': question}), json.dumps({'role': 'assistant', 'content': answer}))

  await redis.expire(f'{r_key}:recent', TTL)


async def clear_conversation_context(workspace_id: str, thread_id: str):
  r_key = f'ctx:{workspace_id}:{thread_id}'

  await redis.delete(f'{r_key}:first', f'{r_key}:recent')