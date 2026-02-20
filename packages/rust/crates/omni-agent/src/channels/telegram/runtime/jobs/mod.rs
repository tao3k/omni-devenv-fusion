mod api;
mod background_completion;
mod command_handlers;
mod command_router;
mod observability;
mod replies;

#[allow(unused_imports)]
pub(in crate::channels::telegram::runtime) use api::{
    handle_inbound_message, log_preview, push_background_completion,
};
