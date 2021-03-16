#include "redismodule.h"

int SimpleCmd2(RedisModuleCtx *ctx, RedisModuleString **argv, int argc)
{
  return RedisModule_ReplyWithSimpleString(ctx,"OK");
}

int RedisModule_OnLoad(RedisModuleCtx *ctx)
{

  // Register the module itself
  if (RedisModule_Init(ctx, "module2", 1, REDISMODULE_APIVER_1) ==
      REDISMODULE_ERR)
  {
    return REDISMODULE_ERR;
  }

  if (RedisModule_CreateCommand(ctx, "module2.cmd2", SimpleCmd2, "readonly",
                                1, 1, 1) == REDISMODULE_ERR)
  {
    return REDISMODULE_ERR;
  }
  return REDISMODULE_OK;
}
