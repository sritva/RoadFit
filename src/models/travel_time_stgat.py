import torch
import torch.nn as nn
import torch.nn.functional as F
try:
    from torch_geometric.nn import GATConv
except ImportError:
    # Fallback/mock if pyg isn't installed yet
    class GATConv(nn.Module):
        def __init__(self, in_channels, out_channels, heads=1, concat=True, dropout=0.0):
            super().__init__()
            self.linear = nn.Linear(in_channels, out_channels * heads)
        def forward(self, x, edge_index):
            return self.linear(x)

class ST_GAT(nn.Module):
    """
    Spatial-Temporal Graph Attention Network for Edge Embeddings.
    This architecture learns structural and difficulty properties of the road network
    to predict latent risk/obstruction values.
    """
    def __init__(self, in_channels, hidden_channels, out_channels, heads=4, dropout=0.2):
        super(ST_GAT, self).__init__()
        
        # Spatial Graph Attention Layers
        self.gat1 = GATConv(in_channels, hidden_channels, heads=heads, dropout=dropout)
        
        # In a real model, we might have temporal layers (e.g. GRU) for time-of-day traffic,
        # but for this foundational architecture, we focus on spatial dependencies of road dimensions.
        self.gat2 = GATConv(hidden_channels * heads, hidden_channels, heads=1, concat=False, dropout=dropout)
        
        # Edge prediction head
        # In our case, we want to predict properties *per edge*. 
        # A simple approach is to concatenate node embeddings to predict edge weight.
        self.edge_predictor = nn.Sequential(
            nn.Linear(hidden_channels * 2, hidden_channels),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_channels, out_channels),
            nn.Softplus() # ensure non-negative weights
        )

    def forward(self, x, edge_index):
        # x: Node feature matrix [num_nodes, in_channels]
        # edge_index: Graph connectivity [2, num_edges]
        
        # 1. Node representation learning
        h = self.gat1(x, edge_index)
        h = F.elu(h)
        h = self.gat2(h, edge_index)
        
        # 2. Edge representation learning (predicting edge risk)
        # Extract source and target node features for each edge
        src_nodes, dst_nodes = edge_index[0], edge_index[1]
        
        h_src = h[src_nodes]
        h_dst = h[dst_nodes]
        
        # Concatenate src and dst features to predict edge property
        edge_features = torch.cat([h_src, h_dst], dim=1)
        
        edge_weights = self.edge_predictor(edge_features)
        return edge_weights.squeeze()
        
if __name__ == "__main__":
    # Simple test of the architecture
    print("Testing ST-GAT Architecture Initialization...")
    model = ST_GAT(in_channels=5, hidden_channels=16, out_channels=1)
    
    # Mock data
    num_nodes = 10
    num_edges = 15
    mock_x = torch.randn((num_nodes, 5))
    mock_edge_index = torch.randint(0, num_nodes, (2, num_edges))
    
    out = model(mock_x, mock_edge_index)
    print(f"Model output shape: {out.shape} (Expected: [{num_edges}])")
    print("ST-GAT Architecture initialized successfully.")
