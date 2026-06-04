import random

class LoadBalancer:
    def __init__(self):
        self.active_env = "blue"
        
    def switch_traffic(self, target_env):
        print(f"Switching traffic to {target_env}")
        self.active_env = target_env

def run_health_check(env) -> bool:
    # Simulates a health check that passes 80% of the time
    return random.random() < 0.8

def deploy_new_version(lb: LoadBalancer):
    # TODO: Implement the blue-green deployment logic here
    # 1. Determine inactive env
    # 2. Deploy to inactive (print statement)
    # 3. Health check
    # 4. Switch traffic or rollback
    pass
