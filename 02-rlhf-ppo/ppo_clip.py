"""The PPO clipped objective, written out so you can play with the numbers."""
import torch


def ppo_loss(logp_new, logp_old, advantages, clip_eps=0.2):
    ratio = torch.exp(logp_new - logp_old)
    unclipped = ratio * advantages
    clipped = torch.clamp(ratio, 1 - clip_eps, 1 + clip_eps) * advantages
    return -torch.min(unclipped, clipped).mean()


if __name__ == "__main__":
    logp_old = torch.log(torch.tensor([0.30, 0.50, 0.20]))
    logp_new = torch.log(torch.tensor([0.45, 0.40, 0.15]))
    adv = torch.tensor([1.0, -0.5, 0.2])
    print("ratio:", torch.exp(logp_new - logp_old))
    print("loss :", ppo_loss(logp_new, logp_old, adv).item())
