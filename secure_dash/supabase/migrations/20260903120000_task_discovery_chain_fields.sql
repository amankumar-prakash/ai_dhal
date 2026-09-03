-- Extra attack-chain step fields for task-discovery (tools / findings categories).
ALTER TABLE public.attack_chain_steps
  ADD COLUMN IF NOT EXISTS category text,
  ADD COLUMN IF NOT EXISTS source_tool text,
  ADD COLUMN IF NOT EXISTS evidence text;
