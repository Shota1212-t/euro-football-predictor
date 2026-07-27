from .prepare_data import run as prepare
from .train_lightgbm import train as train_lgbm
from .train_neural_network import train as train_mlp
from .compare_models import run as compare
if __name__=='__main__':
    prepare(); train_lgbm(); train_mlp(); compare()
