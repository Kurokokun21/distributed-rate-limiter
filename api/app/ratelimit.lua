-- Token bucket rate limiter, runs atomically inside Redis.
-- Inputs handed in by the Python caller:
--   KEYS[1]  = redis key holding this client's bucket (e.g. "ratelimit:1.2.3.4")
--   ARGV[1]  = capacity     (max tokens the bucket can hold = max burst)
--   ARGV[2]  = refill_rate  (tokens added per second = sustained rate)
--   ARGV[3]  = now          (current time in seconds, as a float)
--   ARGV[4]  = requested    (how many tokens this request costs, normally 1)

local key         = KEYS[1]
local capacity    = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now         = tonumber(ARGV[3])
local requested   = tonumber(ARGV[4])

-- Read the bucket's saved state: how many tokens were left, and when we last touched it.
local bucket = redis.call("HMGET", key, "tokens", "timestamp")
local tokens = tonumber(bucket[1])
local last   = tonumber(bucket[2])

-- First time we've ever seen this client -> give them a full bucket.
if tokens == nil then
  tokens = capacity
  last   = now
end

-- Refill: add tokens for the time that has passed since we last saw them,
-- but never overflow past capacity.
local elapsed = math.max(0, now - last)
tokens = math.min(capacity, tokens + elapsed * refill_rate)

-- Decide: is there enough for this request?
local allowed = tokens >= requested
if allowed then
  tokens = tokens - requested
end

-- Save the new state back.
redis.call("HSET", key, "tokens", tokens, "timestamp", now)

-- Auto-clean idle buckets: expire the key after enough time to fully refill.
-- (If the client goes quiet, Redis drops the key; next visit they start full again.)
local ttl = math.ceil(capacity / refill_rate) * 2
redis.call("EXPIRE", key, ttl)

-- Return [allowed?, tokens_left]. Redis floors Lua numbers on the way out.
if allowed then
  return {1, tokens}
else
  return {0, tokens}
end
