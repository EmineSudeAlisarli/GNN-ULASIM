import torch
import torch.nn.functional as F
from torch_geometric.nn import HeteroConv, SAGEConv

import json
from pathlib import Path

# Kodun çalıştığı ana klasörün yolunu alır
BASE_DIR = Path(__file__).resolve().parent

# konya_data.json dosyasının yolunu dinamik olarak belirler
json_path = BASE_DIR / "konya_data.json"

# JSON dosyasını okuma
with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

class RiskPredictorGNN(torch.nn.Module):
    """
    Kaza Risk Tahmini Yapan Heterojen Graf Sinir Ağı Modeli.
    
    Model, yol (road) ve kavşak (intersection) düğümleri üzerinden 
    göreceli kaza risk skoru (0 ile 1 arası değer) üretir.
    """
    def __init__(self, hidden_channels=128, num_layers=4, dropout_rate=0.3):
        super().__init__()
        self.dropout_rate = dropout_rate
        self.convs = torch.nn.ModuleList()
        for _ in range(num_layers):
            conv = HeteroConv({
                ('intersection', 'to', 'road'): SAGEConv((-1, -1), hidden_channels),
                ('road', 'to', 'intersection'): SAGEConv((-1, -1), hidden_channels),
            }, aggr='mean')
            self.convs.append(conv)
            
        self.lin1 = torch.nn.Linear(hidden_channels, 64)
        self.lin2 = torch.nn.Linear(64, 1)

    def forward(self, x_dict, edge_index_dict):
        for conv in self.convs:
            x_dict = conv(x_dict, edge_index_dict)
            x_dict = {key: F.relu(x) for key, x in x_dict.items()}
            x_dict = {key: F.dropout(x, p=self.dropout_rate, training=self.training) for key, x in x_dict.items()}
            
        out = self.lin1(x_dict['road'])
        out = F.relu(out)
        out = F.dropout(out, p=self.dropout_rate, training=self.training)
        
        # Logit çıktısı (ham skor)
        out = self.lin2(out)
        
        # 0 ile 1 arasında Göreceli Risk Skoru döndür
        return torch.sigmoid(out).squeeze()

def load_pretrained_model(model_path, device='cpu'):
    """
    Önceden eğitilmiş bir Pytorch .pth modelini yükler.
    
    Kullanım:
    model = load_pretrained_model('hetero_risk_london.pth')
    """
    model = RiskPredictorGNN(hidden_channels=128, num_layers=4, dropout_rate=0.3).to(device)
    
    # weights_only=True güvenlik uyarısını kapatır ve güvenli yükleme sağlar
    model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
    model.eval()
    
    return model
