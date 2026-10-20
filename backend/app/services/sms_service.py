"""SMS delivery — currently unconfigured, and honest about it.

There is no SMS provider on this deployment. That is a deliberate state, not an
oversight: signing up for one is a procurement decision for CTU, not something
this codebase should fake its way around.

What matters is HOW it is unconfigured. Two tempting shortcuts are both refused:

* **Logging the code instead of sending it.** The obvious "dev mode". It puts
  every OTP into Loki, which more people can read than the database — and the
  whole point of `app/otp.py` is that the code exists in exactly two places, the
  recipient's phone and nowhere else. A dev convenience that violates the
  system's one hard rule is not a dev convenience.
* **Returning success.** Then `verify_phone` appears to work, nobody receives
  anything, and the failure surfaces as "the code never arrives" long after the
  deploy that caused it.

So this raises. A caller that offers SMS on an unconfigured deployment gets an
error it can show the user, at the moment of the attempt.

To enable: implement `send_sms` against the chosen provider and set the
credentials in the environment. The code is passed as an argument and must not
be logged, retained, or included in an exception message.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class SmsNotConfigured(RuntimeError):
    """No SMS provider is configured on this deployment."""


def sms_available() -> bool:
    """Whether `send_sms` can actually deliver.

    Callers use this to decide whether to OFFER the SMS channel, so the person
    is not invited to pick a route that cannot work.
    """
    return False


def send_sms(to_number: str, message: str) -> None:
    """Deliver a message. Raises until a provider is wired up.

    `message` carries the code. Note what is absent: any logging of it, and any
    inclusion of it in the exception below.
    """
    raise SmsNotConfigured(
        "SMS chưa được cấu hình trên hệ thống này; hãy dùng kênh email."
    )
