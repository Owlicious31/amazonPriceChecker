import logging
import os
import smtplib

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(filename)s - %(levelname)s - %(message)s - %(asctime)s")

def load_env_variables(environment: str) -> None:
    """
    Load environment variables.
    :param environment: The current working environment. Either development or demo.
    :return: None
    """
    if environment.lower() == "development":
        if not os.path.exists(".env.development"):
            raise FileNotFoundError(".env.development not found.")

        else:
            load_dotenv(".env.development")
            logging.info(".env.development loaded")
    else:
        if not os.path.exists(".env.demo"):
            raise FileNotFoundError(".env.demo not found.")

        else:
            load_dotenv(".env.demo")
            logging.info(".env.demo loaded")


load_env_variables(environment="demo")

#Info for sending emails
EMAIL: str | None = os.getenv("EMAIL")
EMAIL_PASSWORD: str | None = os.getenv("PASSWORD")
RECIPIENT: str | None = os.getenv("RECIPIENT")
EMAIL_HOST: str = "smtp.gmail.com"
EMAIL_PORT: int = 587

ENV_VARS: dict[str, str | None ] = {
    "EMAIL":EMAIL,
    "EMAIL_PASSWORD":EMAIL_PASSWORD,
    "RECIPIENT":RECIPIENT,
}

load_success: bool = True

for name,var in ENV_VARS.items():
    if not var:
        logging.critical(f"Environment variable failed to load: {name}")
        load_success = False
    else:
        logging.info(f"Loaded environment variable: {name}")

if not load_success:
    raise Exception("Failed to load environment variables.")

#Target price we want for the product
TARGET_PRICE: int = 100

#Product url for Amazon
AMAZON_URL: str = "https://www.amazon.com/dp/B075CYMYK6?ref_=cm_sw_r_cp_ud_ct_FM9M699VKHTT47YD50Q6&th=1"

#Header for GET requests
REQUEST_HEADER: dict = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


#Parser for website source code
PARSER: str = "html.parser"

#Maximum number of times program will attempt to get product information
MAX_RETRIES: int = 5

def get_product_info(parser: str, url: str) -> tuple:
    """
    Fetch the price and name of an Amazon product.
    :param parser: Parser to be used on the website's html.
    :param url: The product's URL.
    :return: listed_price: The product name and price.
    """
    global MAX_RETRIES

    if MAX_RETRIES != 0:
        #Retrieving Amazon html
        response = requests.get(url=url,headers=REQUEST_HEADER)
        response.raise_for_status()
        contents: str = response.text

        #Parsing Amazon html with BeautifulSoup and html parser
        try:
            soup: BeautifulSoup = BeautifulSoup(markup=contents, features=parser)

        except Exception as e:
            logging.critical(f"Error parsing html:{e}")
            quit()

        #Getting the product price
        try:
            price_tag: str = str(soup.select_one(selector="span#size_name_0_price p").text)

        except AttributeError:
            logging.warning("Could not get price text. Retrying...")
            MAX_RETRIES -= 1

            get_product_info(parser=parser, url=url)

        except Exception as e:
            logging.warning(f"Error getting price text:{e}")

        else:
            price_tag = price_tag.strip("\r\n $")

            listed_price: float = float(price_tag)

            #Getting product name
            try:
                price_title_split: list = str(soup.select_one(selector="span#productTitle").text).split()

            except AttributeError:
                logging.warning("Could not get product name. Retrying...")
                MAX_RETRIES -= 1

                get_product_info(parser=parser, url=url)

            except Exception as e:
                logging.warning(f"Error getting product name:{e}")

            else:
                price_title: str = " ".join(price_title_split)

                return price_title,listed_price

    else:
        logging.critical("Max retries exceeded.")
        return ()

def send_mail(email: str, password: str, recipient: str, new_price: float, product_url: str,product_name: str) -> None:
    """
    Send an email notifying the recipient of a price drop in a product they're monitoring.
    :param email: The email sending the message.
    :param password: The password of the email sending the message.
    :param recipient: The recipient of the message.
    :param new_price: The product's current price.
    :param product_url: The URL to view the product.
    :param product_name: The title of the product.
    :return: None
    """
    with smtplib.SMTP(host=EMAIL_HOST, port=EMAIL_PORT) as connection:
        connection.starttls()
        connection.login(
            user=email,
            password=password
        )
        try:
            connection.sendmail(
                from_addr=email,
                to_addrs=recipient,
                msg=f"""Subject:Price decrease on product you're watching!
                \n\n{product_name} just dropped to ${new_price}. Your target price was ${TARGET_PRICE}.
                \rCheck out the product at {product_url}.""".encode("utf-8")
            )

        except Exception as e:
            logging.error(f"Error sending email:{e}")

        else:
            logging.info("Email sent.")


product_info: tuple = get_product_info(url=AMAZON_URL, parser=PARSER)

if not product_info:
    logging.critical("Could not get product info.")

else:
    product: str =  product_info[0]
    logging.info(f"Product name is {product}")

    price: float = product_info[1]
    logging.info(f"Product price is ${price}")

    if price <= TARGET_PRICE:
        send_mail(
            email=EMAIL,
            password=EMAIL_PASSWORD,
            recipient=RECIPIENT,
            new_price=price,
            product_url=AMAZON_URL,
            product_name=product
        )

    else:
        logging.info("No price drop. No email sent.")
