#!/usr/bin/env python3
"""Automated UI Screenshot Capture Script for BC-FL-SRV Research Platform.

Captures all 7 major tabs, 6 modal dialogs, interactive security vectors,
inference testing, blockchain views, and responsive states using Playwright
and headless Google Chrome.
Uses proper .content-area scrolling / scrollIntoView.
"""

import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path("/Users/ayush/Downloads/Study/ui_screenshots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BASE_URL = "http://127.0.0.1:8000"

def run_capture():
    print(f"Starting screenshot capture to {OUT_DIR}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_BIN,
            headless=True,
            args=["--disable-gpu", "--no-sandbox"]
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 960},
            device_scale_factor=1.5  # High-DPI crisp capture
        )
        page = context.new_page()

        # Navigate to Dashboard
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_timeout(2000)

        def scroll_to_el(selector):
            page.evaluate(f"""() => {{
                const el = document.querySelector('{selector}');
                if (el) el.scrollIntoView({{ behavior: 'instant', block: 'start' }});
            }}""")
            page.wait_for_timeout(600)

        def scroll_content(val):
            page.evaluate(f"""() => {{
                const ca = document.querySelector('.content-area');
                if (ca) ca.scrollTop = {val};
            }}""")
            page.wait_for_timeout(600)

        # ------------------------------------------------------------------
        # 1. Dashboard: Top section (Signature Categories & KPIs)
        # ------------------------------------------------------------------
        print("Capturing 01_dashboard_top_kpis.png...")
        scroll_content(0)
        page.screenshot(path=str(OUT_DIR / "01_dashboard_top_kpis.png"))

        # ------------------------------------------------------------------
        # 2. Dashboard: Parameters Matrix & Research Charts Grid
        # ------------------------------------------------------------------
        print("Capturing 02_dashboard_parameters_and_charts.png...")
        scroll_to_el(".academic-matrix-grid")
        page.screenshot(path=str(OUT_DIR / "02_dashboard_parameters_and_charts.png"))

        # ------------------------------------------------------------------
        # 3. Dashboard: Recent Blockchain Model Uploads Table
        # ------------------------------------------------------------------
        print("Capturing 03_dashboard_recent_blockchain_uploads.png...")
        scroll_to_el("#dashboard-uploads-table-body")
        page.screenshot(path=str(OUT_DIR / "03_dashboard_recent_blockchain_uploads.png"))

        # ------------------------------------------------------------------
        # 4. Modal: Comprehensive Academic Audit (5 Pillars)
        # ------------------------------------------------------------------
        print("Capturing 04_modal_academic_audit.png...")
        scroll_content(0)
        page.evaluate("runAcademicAudit()")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT_DIR / "04_modal_academic_audit.png"))
        page.evaluate("document.getElementById('system-audit-modal').classList.remove('active')")
        page.wait_for_timeout(500)

        # ------------------------------------------------------------------
        # 5. Modal: Model Verification on 10k Test Set
        # ------------------------------------------------------------------
        print("Capturing 05_modal_model_verification_testset.png...")
        page.evaluate("verifyModelTestSet()")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT_DIR / "05_modal_model_verification_testset.png"))
        page.evaluate("document.getElementById('model-verify-modal').classList.remove('active')")
        page.wait_for_timeout(500)

        # ------------------------------------------------------------------
        # 6. Modal: Pipeline Stage Latency Waterfall
        # ------------------------------------------------------------------
        print("Capturing 06_modal_stage_latencies_waterfall.png...")
        page.evaluate("showLatencyModal()")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT_DIR / "06_modal_stage_latencies_waterfall.png"))
        page.evaluate("document.getElementById('latency-modal').classList.remove('active')")
        page.wait_for_timeout(500)

        # ------------------------------------------------------------------
        # 7. Modal: High-Res Expanded Accuracy Chart
        # ------------------------------------------------------------------
        print("Capturing 07_modal_chart_expanded_accuracy.png...")
        page.evaluate("expandChart('accuracy')")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT_DIR / "07_modal_chart_expanded_accuracy.png"))
        page.evaluate("document.getElementById('chart-expand-modal').classList.remove('active')")
        page.wait_for_timeout(500)

        # ------------------------------------------------------------------
        # 8. FL Clients Tab: Overview & Permanent Trust Ledger Table
        # ------------------------------------------------------------------
        print("Capturing 08_clients_overview_trust_ledger.png...")
        page.click("li.nav-item[data-tab='clients']")
        page.wait_for_timeout(1000)
        scroll_content(0)
        page.screenshot(path=str(OUT_DIR / "08_clients_overview_trust_ledger.png"))

        # ------------------------------------------------------------------
        # 9. FL Clients Tab: Weights & Gradient Delta Transparency Grid
        # ------------------------------------------------------------------
        print("Capturing 09_clients_weights_transparency_grid.png...")
        scroll_to_el("#clients-weights-grid")
        page.screenshot(path=str(OUT_DIR / "09_clients_weights_transparency_grid.png"))

        # ------------------------------------------------------------------
        # 10. FL Clients Tab: Training Activity & Cryptographic Proof Stream
        # ------------------------------------------------------------------
        print("Capturing 10_clients_training_logs_stream.png...")
        scroll_to_el("#client-logs-terminal")
        page.screenshot(path=str(OUT_DIR / "10_clients_training_logs_stream.png"))

        # ------------------------------------------------------------------
        # 11. Modal: Client Deep Transparency (Non-IID Shard Distribution)
        # ------------------------------------------------------------------
        print("Capturing 11_modal_client_deep_transparency.png...")
        page.evaluate("""() => {
            const firstBtn = document.querySelector('#clients-table-body button');
            if (firstBtn) firstBtn.click();
        }""")
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT_DIR / "11_modal_client_deep_transparency.png"))
        page.evaluate("document.getElementById('weights-modal').classList.remove('active')")
        page.wait_for_timeout(500)

        # ------------------------------------------------------------------
        # 12. FL Training Room Tab: Parameters & Progress Monitor
        # ------------------------------------------------------------------
        print("Capturing 12_training_room_overview.png...")
        page.click("li.nav-item[data-tab='training']")
        page.wait_for_timeout(1000)
        scroll_content(0)
        page.screenshot(path=str(OUT_DIR / "12_training_room_overview.png"))

        # ------------------------------------------------------------------
        # 13. FL Training Room: Injected Malicious Rogue Node State
        # ------------------------------------------------------------------
        print("Capturing 13_training_room_malicious_injected.png...")
        page.click("#btn-inject-malice")
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT_DIR / "13_training_room_malicious_injected.png"))

        # ------------------------------------------------------------------
        # 14. Blockchain Explorer: Quorum Nodes HUD
        # ------------------------------------------------------------------
        print("Capturing 14_blockchain_quorum_nodes_hud.png...")
        page.click("li.nav-item[data-tab='blockchain']")
        page.wait_for_timeout(1000)
        scroll_content(0)
        page.screenshot(path=str(OUT_DIR / "14_blockchain_quorum_nodes_hud.png"))

        # ------------------------------------------------------------------
        # 15. Blockchain Explorer: Sealed Ledger Blocks Feed
        # ------------------------------------------------------------------
        print("Capturing 15_blockchain_sealed_blocks_feed.png...")
        scroll_to_el("#timeline-container")
        page.screenshot(path=str(OUT_DIR / "15_blockchain_sealed_blocks_feed.png"))

        # ------------------------------------------------------------------
        # 16. Blockchain Explorer: Client Tx Uploads View
        # ------------------------------------------------------------------
        print("Capturing 16_blockchain_client_tx_uploads.png...")
        page.click("#pill-uploads")
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT_DIR / "16_blockchain_client_tx_uploads.png"))

        # ------------------------------------------------------------------
        # 17. Blockchain Explorer: Verify Hash Chain Action
        # ------------------------------------------------------------------
        print("Capturing 17_blockchain_hash_chain_verified.png...")
        page.click("#pill-all-blocks")
        page.wait_for_timeout(400)
        scroll_content(0)
        page.click("#btn-verify-chain")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT_DIR / "17_blockchain_hash_chain_verified.png"))
        page.evaluate("document.getElementById('client-modal').classList.remove('active')")
        page.wait_for_timeout(500)

        # ------------------------------------------------------------------
        # 18. Blockchain Explorer: Block Payload JSON Modal
        # ------------------------------------------------------------------
        print("Capturing 18_modal_block_payload_json.png...")
        page.evaluate("showBlockModal(1)")
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT_DIR / "18_modal_block_payload_json.png"))
        page.evaluate("document.getElementById('client-modal').classList.remove('active')")
        page.wait_for_timeout(500)

        # ------------------------------------------------------------------
        # 19. Model & Inference: Architecture Summary & Parameter Stats
        # ------------------------------------------------------------------
        print("Capturing 19_model_architecture_and_stats.png...")
        page.click("li.nav-item[data-tab='model']")
        page.wait_for_timeout(1000)
        scroll_content(0)
        page.screenshot(path=str(OUT_DIR / "19_model_architecture_and_stats.png"))

        # ------------------------------------------------------------------
        # 20. Model & Inference: Fashion-MNIST Gallery & Live Prediction
        # ------------------------------------------------------------------
        print("Capturing 20_model_interactive_gallery_and_prediction.png...")
        page.wait_for_selector(".sample-card", timeout=10000)
        page.click(".sample-card:first-child")
        page.wait_for_timeout(1200)
        scroll_to_el(".sample-grid")
        page.screenshot(path=str(OUT_DIR / "20_model_interactive_gallery_and_prediction.png"))

        # ------------------------------------------------------------------
        # 21. Model & Inference: Custom Image Upload Section
        # ------------------------------------------------------------------
        print("Capturing 21_model_custom_image_upload.png...")
        scroll_to_el("#upload-preview")
        page.screenshot(path=str(OUT_DIR / "21_model_custom_image_upload.png"))

        # ------------------------------------------------------------------
        # 22. Security Operations Center (SOC): Banner & Real-Time Threat HUD
        # ------------------------------------------------------------------
        print("Capturing 22_security_soc_banner_and_hud.png...")
        page.click("li.nav-item[data-tab='security']")
        page.wait_for_timeout(1000)
        scroll_content(0)
        page.screenshot(path=str(OUT_DIR / "22_security_soc_banner_and_hud.png"))

        # ------------------------------------------------------------------
        # 23. Security Operations Center: 6 Interactive Threat Vectors
        # ------------------------------------------------------------------
        print("Capturing 23_security_threat_injection_vectors.png...")
        scroll_to_el(".threat-card")
        page.screenshot(path=str(OUT_DIR / "23_security_threat_injection_vectors.png"))

        # ------------------------------------------------------------------
        # 24. Security Operations Center: Attack Intercepted Forensic Modal & Banner
        # ------------------------------------------------------------------
        print("Capturing 24_security_attack_intercepted_modal.png...")
        page.click("#btn-attack-tamper")
        page.wait_for_timeout(2500)
        page.screenshot(path=str(OUT_DIR / "24_security_attack_intercepted_modal.png"))
        page.evaluate("document.getElementById('client-modal').classList.remove('active')")
        page.wait_for_timeout(600)
        scroll_to_el("#attack-result-banner")
        print("Capturing 24b_security_attack_result_banner.png...")
        page.screenshot(path=str(OUT_DIR / "24b_security_attack_result_banner.png"))

        # ------------------------------------------------------------------
        # 25. Security Operations Center: Live Threat Interception Feed
        # ------------------------------------------------------------------
        print("Capturing 25_security_forensic_incident_feed.png...")
        scroll_to_el("#threat-feed-body")
        page.screenshot(path=str(OUT_DIR / "25_security_forensic_incident_feed.png"))

        # ------------------------------------------------------------------
        # 26. Live Event Logs: Real-Time Event Feed & Controls
        # ------------------------------------------------------------------
        print("Capturing 26_logs_realtime_event_feed.png...")
        page.click("li.nav-item[data-tab='logs']")
        page.wait_for_timeout(1000)
        scroll_content(0)
        page.screenshot(path=str(OUT_DIR / "26_logs_realtime_event_feed.png"))

        # ------------------------------------------------------------------
        # 27. Live Event Logs: Filtered Security Category View
        # ------------------------------------------------------------------
        print("Capturing 27_logs_filtered_security.png...")
        page.click("#log-filter-security")
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT_DIR / "27_logs_filtered_security.png"))

        # ------------------------------------------------------------------
        # 28. Responsive / Tablet Layout View
        # ------------------------------------------------------------------
        print("Capturing 28_responsive_tablet_view.png...")
        context_mobile = browser.new_context(
            viewport={"width": 820, "height": 1024},
            device_scale_factor=1.5
        )
        page_mobile = context_mobile.new_page()
        page_mobile.goto(BASE_URL, wait_until="networkidle")
        page_mobile.wait_for_timeout(1500)
        page_mobile.evaluate("""() => {
            const ca = document.querySelector('.content-area');
            if (ca) ca.scrollTop = 0;
        }""")
        page_mobile.screenshot(path=str(OUT_DIR / "28_responsive_tablet_view.png"))
        context_mobile.close()

        context.close()
        browser.close()
        print("All screenshots successfully captured and saved to ui_screenshots/!")

if __name__ == "__main__":
    run_capture()
