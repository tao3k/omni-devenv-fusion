mod background;
mod dispatch;
mod foreground;
mod session;

pub(in crate::channels::telegram::runtime::jobs) use dispatch::handle_inbound_message;
