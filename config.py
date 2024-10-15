import yaml
import os

class Config:
    def __init__(self, name: str):
        object.__setattr__(self, 'properties', {})
        object.__setattr__(self, 'pathname', os.path.join(os.path.dirname(__file__), name))
    
    def __getattr__(self, name: str):
        return self.properties.get(name)
    
    def __setattr__(self, name: str, value):
        self.properties.update({name: value})
    
    @classmethod
    def load(cls, name: str):
        config = cls(name)
        pathname = os.path.join(os.path.dirname(__file__), name)
        with open(pathname, 'r', encoding = 'utf-8') as file:
            config.properties.update(yaml.load(file, Loader = yaml.FullLoader))
        return config
    
    def save(self):
        with open(self.pathname, 'w', encoding = 'utf-8') as file:
            yaml.dump(self.properties, file, indent = 4)

    def __str__(self) -> str:
        return str(self.properties)


def test():
    config = Config('test.yaml')
    config.user = 'ivan.av'
    config.password = 'qwerty'
    config.save()

    config = Config.load('test.yaml')
    print(config)

if __name__ == '__main__':
    test()