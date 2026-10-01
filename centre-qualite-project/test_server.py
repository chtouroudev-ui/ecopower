#!/usr/bin/env python3
"""Simple test server to demo the improved UI without full backend"""

import json
import http.server
import socketserver
from pathlib import Path

PORT = 9051
BASE_DIR = Path(__file__).parent

class TestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Serve the main HTML
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(self.get_live_supervision_html().encode())
            return

        # Serve API for live supervision
        if self.path == '/api/live/supervision':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(self.get_mock_data()).encode())
            return

        # Serve static files
        if self.path.startswith('/static/'):
            file_path = BASE_DIR / self.path[1:]
            if file_path.exists():
                self.send_response(200)
                if file_path.suffix == '.css':
                    self.send_header('Content-type', 'text/css')
                elif file_path.suffix == '.js':
                    self.send_header('Content-type', 'application/javascript')
                self.end_headers()
                self.wfile.write(file_path.read_bytes())
                return

        # 404
        self.send_response(404)
        self.end_headers()

    def get_live_supervision_html(self):
        return '''<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Centre Qualité Live - Test</title>
  <link rel="stylesheet" href="/static/style.css">
  <link rel="stylesheet" href="/static/quality.css">
  <link rel="stylesheet" href="/static/live-views-improved.css">
  <style>
    body { background: #f5f5f5; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto; }
    .shell { max-width: 1400px; margin: 20px auto; }
    .header { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .header h1 { margin: 0; color: #2d3748; }
    .header p { margin: 5px 0 0 0; color: #718096; }
  </style>
</head>
<body>
  <div class="shell">
    <div class="header">
      <h1>🎯 Centre Qualité Live - Interface Améliorée</h1>
      <p>Test local des améliorations UI/UX (Agents groupés, Campagnes en grille, Filtres persistants)</p>
    </div>
    <div id="live-agents-panel"></div>
  </div>

  <script src="/static/live-views-improvements.js"></script>
  <script>
    // Initialize with mock data
    const mockData = {
      agents: [
        { agent: '571', name: 'Agent 571', state: 'call', kind: 'call', group_id: 'MED', group: 'GROUPE MED', group_name: 'GROUPE MED',
          campaign: 'CAM-01', campaign_name: 'Campagne 1', quality_score: 89,
          call_duration_seconds: 165, pause_duration_seconds: 7800 },
        { agent: '572', name: 'Agent 572', state: 'pause', kind: 'pause', group_id: 'MED', group: 'GROUPE MED', group_name: 'GROUPE MED',
          campaign: 'CAM-02', campaign_name: 'Campagne 2', quality_score: 92,
          call_duration_seconds: 0, pause_duration_seconds: 900 },
        { agent: '601', name: 'Agent 601', state: 'call', kind: 'call', group_id: 'OUD', group: 'GROUPE OUD', group_name: 'GROUPE OUD',
          campaign: 'CAM-01', campaign_name: 'Campagne 1', quality_score: 88,
          call_duration_seconds: 83, pause_duration_seconds: 6900 },
        { agent: '602', name: 'Agent 602', state: 'ready', kind: 'ready', group_id: 'OUD', group: 'GROUPE OUD', group_name: 'GROUPE OUD',
          campaign: 'CAM-03', campaign_name: 'Campagne 3', quality_score: 95,
          call_duration_seconds: 0, pause_duration_seconds: 0 },
        { agent: '603', name: 'Agent 603', state: 'offline', kind: 'offline', group_id: 'OUD', group: 'GROUPE OUD', group_name: 'GROUPE OUD',
          campaign: 'CAM-01', campaign_name: 'Campagne 1', quality_score: 0,
          call_duration_seconds: 0, pause_duration_seconds: 0 },
      ]
    };

    // Normalize states for mapping
    function normalizeStateForDisplay(state, kind) {
      if (kind === 'call' || state === 'call') return 'in_call';
      if (kind === 'ready' || state === 'ready') return 'available';
      if (kind === 'pause' || state === 'pause') return 'pause';
      if (kind === 'offline' || state === 'offline') return 'offline';
      return 'unobserved';
    }

    // Map mock data to rendering format
    mockData.agents = mockData.agents.map(a => ({
      ...a,
      state: normalizeStateForDisplay(a.state, a.kind),
      kind: normalizeStateForDisplay(a.state, a.kind)
    }));

    // Initialize filters
    if (window.LiveImprovements) {
      const filters = window.LiveImprovements.filters.agentFilters.state;

      // Render agents
      const html = window.LiveImprovements.renderAgentsImproved(mockData, filters);
      document.getElementById('live-agents-panel').innerHTML = html;

      // Setup event handlers
      window.handleAgentFilterChange = function(key, value) {
        filters[key] = value;
        const html = window.LiveImprovements.renderAgentsImproved(mockData, filters);
        document.getElementById('live-agents-panel').innerHTML = html;
      };
    }
  </script>
</body>
</html>'''

    def get_mock_data(self):
        return {
            "health": {"fresh": True, "label": "Connecté", "connection_state": "OK"},
            "agents": [
                {"agent": "571", "name": "Agent 571", "state": "in_call", "kind": "call"},
                {"agent": "572", "name": "Agent 572", "state": "pause", "kind": "pause"},
            ],
            "quality": {"center": {}},
            "kpi": {"connected": 2, "available": 1}
        }

if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), TestHandler) as httpd:
        print(f"🚀 Serveur de test lancé sur http://localhost:{PORT}")
        print(f"📍 Centre Qualité Live: http://localhost:{PORT}/")
        print(f"\n✨ Interface améliorée avec:")
        print(f"   ✓ Agents groupés par unité organisationnelle")
        print(f"   ✓ États colorés avec icônes (🔴 EN APPEL, 🟢 DISPONIBLE, etc.)")
        print(f"   ✓ Filtres persistants (État, Groupe, Campagne, Recherche)")
        print(f"   ✓ Responsive design sans scroll horizontal")
        httpd.serve_forever()
