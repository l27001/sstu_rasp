from telebot.custom_filters import AdvancedCustomFilter


def split_inline_query(message):
        message.data = message.data.split("/")
        if(len(message.data) < 2):
             message.data.append("")
        message.data[1] = message.data[1].split(",")
        return 1


class CallbackDataFilter(AdvancedCustomFilter):
    """
    Filter to check callback data.
    Data previously must be splitted by using split_inline_query.

    .. code-block:: python3
        :caption: Example on using this filter:

        @bot.message_handler(callback_data=['account'])
        # your function
    """

    key='callback_data'

    @staticmethod
    def check(message, arg):
        if(type(arg) is list):
            return message.data[0] in arg
        else:
            return message.data[0] == arg
