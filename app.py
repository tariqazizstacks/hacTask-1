"""
app.py
======
The Gradio interface. Wiring only.

Every decision and every string that is not a component label comes from
src/ui_logic.py, which has no Gradio dependency and is unit-tested. This file
lays out components and connects them to those functions. If you find
yourself writing an if-statement here, it probably belongs in ui_logic.

Run it:
    python app.py                  (local)
    !python app.py                 (Colab)

or from inside a notebook cell:
    from app import demo
    demo.launch(share=True)

Tabs:
    Home                  entry point and example prompts
    AI Assistant          chat, extracted summary, ranked providers   (Stage 9)
    Find a Professional   dropdown browsing, no AI needed
    My Service Request    booking form and confirmation               (Stage 10)
    Dashboard             submitted requests, and analytics           (Stage 12)
    About                 how it works, scoring, safety, data notice
"""

from __future__ import annotations

import gradio as gr

import analytics as analytics_mod
from src import config, ui_logic

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
# One font family, a teal primary and a slate neutral. IBM Plex Sans is a
# plain utilitarian face -- it suits an app about getting a broken thing
# fixed, and it is not the default Gradio look, so the app does not read as
# an untouched template.

THEME = gr.themes.Base(
    primary_hue=gr.themes.colors.teal,
    secondary_hue=gr.themes.colors.slate,
    neutral_hue=gr.themes.colors.slate,
    font=[gr.themes.GoogleFont("IBM Plex Sans"), "ui-sans-serif", "sans-serif"],
).set(
    body_background_fill="#f7f9fa",
    block_border_width="1px",
    block_radius="6px",
    button_primary_background_fill="#0e7c86",
    button_primary_background_fill_hover="#0a5c64",
)


def _load_css() -> str:
    path = config.ASSETS_DIR / "style.css"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""      # the app must still run if the stylesheet is missing


# ---------------------------------------------------------------------------
# Handlers that are already live at this stage
# ---------------------------------------------------------------------------
# The AI Assistant and My Service Request tabs are laid out but not yet
# connected; those arrive in Stages 9 and 10. Everything below works now.

def on_browse(category, area, availability, min_rating):
    return ui_logic.browse_providers(category, area, availability, min_rating)


def on_dashboard_refresh(status):
    """Redraw the table, the headline and every chart from one data read."""
    table, note = ui_logic.dashboard_table(status)
    stats = ui_logic.analytics_bundle()
    return (
        table,
        note,
        ui_logic.dashboard_summary(),
        gr.update(choices=ui_logic.request_id_choices()),
        stats["metrics_md"],
        stats["by_category"],
        stats["by_status"],
        stats["by_value"],
        stats["over_time"],
        stats["insights_md"],
    )


# --- booking ---------------------------------------------------------------

def on_submit(name, phone, area, address, problem, date, time_slot, notes,
              provider, slots):
    """
    Save the booking, then refresh the dashboard in the same action.

    Refreshing here rather than making the user press Refresh is what makes
    the demo flow work: submit on one tab, switch to the dashboard, and the
    row is already there.
    """
    result = ui_logic.submit_booking(name, phone, area, address, problem,
                                     date, time_slot, notes, provider, slots)
    blank = result["clear_form"]
    return (
        result["message_md"],                       # booking_result
        gr.update(value="" if blank else name),     # form_name
        gr.update(value="" if blank else phone),    # form_phone
        gr.update(value="" if blank else address),  # form_address
        gr.update(value="" if blank else notes),    # form_notes
        # the whole dashboard, table and charts, in the same action
        *on_dashboard_refresh("All"),
    )


def on_change_status(request_id, status, current_filter):
    message = ui_logic.change_status(request_id, status)
    return (message, *on_dashboard_refresh(current_filter))


def on_example_click(prompt: str):
    """Copy an example prompt into the chat box and move to that tab."""
    return prompt, gr.Tabs(selected="assistant")


# --- AI Assistant ----------------------------------------------------------

def on_send(message, history, slots):
    """
    One turn of the conversation.

    All the thinking happens in ui_logic.process_message; this function only
    converts its plain return values into Gradio updates. The message box is
    cleared by returning an empty string to it.
    """
    turn = ui_logic.process_message(message, history, slots)
    return (
        turn["history"],                                   # chatbot
        turn["history"],                                   # history_state
        turn["slots"],                                     # slots_state
        turn["matches"],                                   # matches_state
        turn["summary_md"],                                # summary_panel
        turn["cards_html"],                                # cards_html
        gr.update(choices=turn["choices"], value=None),    # provider_choice
        turn["note_md"],                                   # matches_note
        "",                                                # message_box
        gr.update(visible=False),                          # to_booking_button
        "",                                                # breakdown_panel
    )


def on_select_provider(choice, matches, slots):
    picked = ui_logic.select_provider(choice, matches, slots)
    return (
        picked["provider"],                                # selected_state
        picked["breakdown_md"],                            # breakdown_panel
        picked["booking_md"],                              # selected_summary
        gr.update(visible=picked["can_book"]),             # to_booking_button
    )


def on_clear():
    blank = ui_logic.reset_conversation()
    return (
        [], [], {}, None, None,
        blank["summary_md"], blank["cards_html"],
        gr.update(choices=[], value=None), "", "",
        gr.update(visible=False),
        "_No professional selected yet. Use the AI Assistant tab to find one._",
    )


def on_continue_to_booking(slots, provider):
    """Carry what we already know across to the booking form."""
    slots = slots or {}
    return (
        gr.Tabs(selected="booking"),
        slots.get("area"),
        slots.get("problem_summary") or "",
        slots.get("preferred_date") or "",
        slots.get("preferred_time"),
    )


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------

def build_ui() -> gr.Blocks:
    with gr.Blocks(theme=THEME, css=_load_css(), title=config.APP_NAME) as demo:

        # --- shared state -------------------------------------------------
        # Gradio's equivalent of Streamlit's session_state. Every value that
        # has to survive between clicks lives here rather than in a module
        # global, because a global would be shared across all visitors to a
        # share=True link.
        slots_state = gr.State({})       # what the assistant understood
        matches_state = gr.State(None)   # the ranked DataFrame
        selected_state = gr.State(None)  # the chosen provider dict
        history_state = gr.State([])     # chat turns sent to the model

        banner = gr.Markdown(ui_logic.startup_banner())

        with gr.Tabs() as tabs:

            # ============================================== Home
            with gr.Tab("Home", id="home"):
                gr.Markdown(ui_logic.home_markdown())
                with gr.Row():
                    example_buttons = [
                        gr.Button(text, size="sm", variant="secondary")
                        for text in config.EXAMPLE_PROMPTS
                    ]
                gr.Markdown(ui_logic.home_footer_markdown())

            # ============================================== AI Assistant
            with gr.Tab("AI Assistant", id="assistant"):
                with gr.Row():
                    with gr.Column(scale=5):
                        chatbot = gr.Chatbot(
                            type="messages",
                            height=380,
                            label="Conversation",
                            show_copy_button=True,
                        )
                        with gr.Row():
                            message_box = gr.Textbox(
                                placeholder="Describe the problem, for example: my AC is leaking water and not cooling",
                                show_label=False,
                                scale=6,
                                autofocus=True,
                            )
                            send_button = gr.Button("Send", variant="primary", scale=1)
                        clear_button = gr.Button("Start over", size="sm")

                    with gr.Column(scale=4):
                        summary_panel = gr.Markdown(
                            "_Your problem summary will appear here._",
                            label="What the assistant understood",
                        )

                gr.Markdown("### Matching professionals")
                matches_note = gr.Markdown("")
                cards_html = gr.HTML(ui_logic.provider_cards_html(None))
                # Selection lives in a radio rather than a button on each
                # card: Gradio cannot attach a working click handler to
                # markup generated inside gr.HTML.
                provider_choice = gr.Radio(
                    choices=[], label="Choose a professional", interactive=True
                )
                breakdown_panel = gr.Markdown("")
                to_booking_button = gr.Button(
                    "Continue to booking", variant="primary", visible=False
                )

            # ============================================== Find a Professional
            with gr.Tab("Find a Professional", id="browse"):
                gr.Markdown(
                    "Already know what you need? Filter the directory directly."
                )
                with gr.Row():
                    browse_category = gr.Dropdown(
                        ["Any service"] + config.SERVICE_CATEGORIES,
                        value="Any service", label="Service",
                    )
                    browse_area = gr.Dropdown(
                        ["Any area"] + config.AREAS,
                        value="Any area", label="Area",
                    )
                    browse_availability = gr.Dropdown(
                        ["Any time"] + config.AVAILABILITY_OPTIONS,
                        value="Any time", label="Availability",
                    )
                    browse_rating = gr.Slider(
                        0, 5, value=0, step=0.5, label="Minimum rating",
                    )
                browse_note = gr.Markdown("")
                browse_table = gr.Dataframe(
                    headers=ui_logic.BROWSE_COLUMNS,
                    interactive=False,
                    wrap=True,
                )

            # ============================================== My Service Request
            with gr.Tab("My Service Request", id="booking"):
                gr.Markdown("### Book a professional")
                selected_summary = gr.Markdown(
                    "_No professional selected yet. Use the AI Assistant tab "
                    "to find one._"
                )
                with gr.Row():
                    form_name = gr.Textbox(label="Your name")
                    form_phone = gr.Textbox(label="Phone number",
                                            placeholder="0300-1234567")
                with gr.Row():
                    form_area = gr.Dropdown(config.AREAS, label="Area")
                    form_date = gr.Textbox(label="Preferred date (YYYY-MM-DD)")
                    form_time = gr.Dropdown(config.TIME_SLOTS,
                                            label="Preferred time")
                form_address = gr.Textbox(label="Address")
                form_problem = gr.Textbox(label="Describe the problem", lines=3)
                form_notes = gr.Textbox(label="Anything else we should know",
                                        lines=2)
                submit_button = gr.Button("Submit request", variant="primary")
                booking_result = gr.Markdown("")

            # ============================================== Dashboard
            with gr.Tab("Dashboard", id="dashboard"):
                dashboard_headline = gr.Markdown(ui_logic.dashboard_summary())
                with gr.Row():
                    dashboard_status = gr.Dropdown(
                        ui_logic.status_filter_choices(),
                        value="All", label="Filter by status", scale=2,
                    )
                    dashboard_refresh = gr.Button("Refresh", scale=1)
                dashboard_note = gr.Markdown("")
                dashboard_data = gr.Dataframe(
                    headers=ui_logic.DASHBOARD_COLUMNS,
                    interactive=False,
                    wrap=True,
                )
                with gr.Accordion("Update a request status", open=False):
                    gr.Markdown(
                        "In a live service this would be driven by the "
                        "professional's own app. Here it is manual so the "
                        "status mix on the analytics tab can be demonstrated."
                    )
                    with gr.Row():
                        status_request_id = gr.Dropdown(
                            ui_logic.request_id_choices(),
                            label="Request reference", scale=3,
                        )
                        status_new_value = gr.Dropdown(
                            list(config.REQUEST_STATUSES),
                            label="New status", scale=2,
                        )
                        status_apply = gr.Button("Apply", scale=1)
                    status_message = gr.Markdown("")
                gr.Markdown("## Analytics")
                analytics_metrics = gr.Markdown(ui_logic.analytics_bundle()["metrics_md"])
                with gr.Row():
                    chart_category = gr.BarPlot(
                        x=analytics_mod.CHART_CATEGORY[0],
                        y=analytics_mod.CHART_CATEGORY[1],
                        title="Requests by service", height=280,
                    )
                    chart_status = gr.BarPlot(
                        x=analytics_mod.CHART_STATUS[0],
                        y=analytics_mod.CHART_STATUS[1],
                        title="Request status", height=280,
                    )
                with gr.Row():
                    chart_value = gr.BarPlot(
                        x=analytics_mod.CHART_VALUE[0],
                        y=analytics_mod.CHART_VALUE[1],
                        title="Estimated value by service", height=280,
                    )
                    chart_time = gr.BarPlot(
                        x=analytics_mod.CHART_TIME[0],
                        y=analytics_mod.CHART_TIME[1],
                        title="Requests per week", height=280,
                    )
                analytics_notes = gr.Markdown("")

            # ============================================== About
            with gr.Tab("About", id="about"):
                gr.Markdown(ui_logic.about_markdown())

        # -------------------------------------------------------------
        # Events
        # -------------------------------------------------------------
        # --- AI Assistant -------------------------------------------------
        send_outputs = [chatbot, history_state, slots_state, matches_state,
                        summary_panel, cards_html, provider_choice,
                        matches_note, message_box, to_booking_button,
                        breakdown_panel]
        send_inputs = [message_box, history_state, slots_state]

        send_button.click(fn=on_send, inputs=send_inputs, outputs=send_outputs)
        # Enter in the textbox does the same thing. People expect this and
        # notice immediately when it is missing.
        message_box.submit(fn=on_send, inputs=send_inputs, outputs=send_outputs)

        provider_choice.change(
            fn=on_select_provider,
            inputs=[provider_choice, matches_state, slots_state],
            outputs=[selected_state, breakdown_panel, selected_summary,
                     to_booking_button],
        )

        clear_button.click(
            fn=on_clear,
            outputs=[chatbot, history_state, slots_state, matches_state,
                     selected_state, summary_panel, cards_html,
                     provider_choice, matches_note, breakdown_panel,
                     to_booking_button, selected_summary],
        )

        to_booking_button.click(
            fn=on_continue_to_booking,
            inputs=[slots_state, selected_state],
            outputs=[tabs, form_area, form_problem, form_date, form_time],
        )

        for button, prompt in zip(example_buttons, config.EXAMPLE_PROMPTS):
            button.click(
                fn=lambda text=prompt: on_example_click(text),
                outputs=[message_box, tabs],
            )

        browse_inputs = [browse_category, browse_area,
                         browse_availability, browse_rating]
        for control in browse_inputs:
            control.change(fn=on_browse, inputs=browse_inputs,
                           outputs=[browse_table, browse_note])

        dashboard_outputs = [dashboard_data, dashboard_note,
                             dashboard_headline, status_request_id,
                             analytics_metrics, chart_category, chart_status,
                             chart_value, chart_time, analytics_notes]

        submit_button.click(
            fn=on_submit,
            inputs=[form_name, form_phone, form_area, form_address,
                    form_problem, form_date, form_time, form_notes,
                    selected_state, slots_state],
            outputs=[booking_result, form_name, form_phone, form_address,
                     form_notes] + dashboard_outputs,
        )

        status_apply.click(
            fn=on_change_status,
            inputs=[status_request_id, status_new_value, dashboard_status],
            outputs=[status_message] + dashboard_outputs,
        )

        dashboard_refresh.click(
            fn=on_dashboard_refresh,
            inputs=[dashboard_status],
            outputs=dashboard_outputs,
        )
        dashboard_status.change(
            fn=on_dashboard_refresh,
            inputs=[dashboard_status],
            outputs=dashboard_outputs,
        )

        # Populate the data-driven tabs on first load, and refresh the
        # banner in case the API key was added after import.
        demo.load(fn=ui_logic.startup_banner, outputs=[banner])
        demo.load(fn=on_browse, inputs=browse_inputs,
                  outputs=[browse_table, browse_note])
        demo.load(fn=on_dashboard_refresh, inputs=[dashboard_status],
                  outputs=dashboard_outputs)

    return demo


demo = build_ui()


if __name__ == "__main__":
    config.ensure_dirs()
    # share=True gives a public link that lasts 72 hours, which is the
    # simplest way to hand the running app to an evaluator.
    demo.launch(share=True, debug=True)
