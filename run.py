import json
import time
from requests import get, put


def read_config():
    with open("config.json", "r") as jsonfile:
        return json.load(jsonfile)


def get_ip():
    return get('https://api.ipify.org').content.decode('utf8')


class main:

    def update_config(self):
        # clear file content before updating the file to prevent issues
        with open("config.json", "w") as file:
            file.close()

        with open("config.json", "r+") as jsonfile:
            json.dump(self.config, jsonfile, indent=4)

        self.config = read_config()

    def run(self):
        print("Running Cloudflare DynDNS script..")
        print("Retrieve current ip address..")

        # get current external ip address
        ip = get_ip()
        print("Current ip address is: {}".format(ip))

        # compare old and new ip address
        old_ip = self.config["ip"]
        print("Old ip address is: {}".format(old_ip))

        if old_ip == ip:
            print("Old and new IP are the same. Stopping script..")
            return

        # we need to update the dns records
        urls = self.config["urls"]

        for url in urls:
            if url["zone_id"] is not None:
                zone_id = url["zone_id"]
            else:
                if self.zone_id_request is not None:
                    zone_id_request = self.zone_id_request
                else:
                    zone_id_request = get(
                        "https://api.cloudflare.com/client/v4/zones?name={}&status=active".format(url["name"]),
                        headers={
                            "X-Auth-Email": self.config["cloudflare_email"],
                            "X-Auth-Key": self.config["cloudflare_api_key"],
                            "Content-Type": "application/json"
                        })

                result = zone_id_request.json()["result"]
                zone_id = result[0]["id"]

                # change zone id in the config
                url["zone_id"] = zone_id
                self.zone_id_request = zone_id_request

            print("Zone id is {} for url {}".format(zone_id, url["name"]))

            for dns_record in url["dns_records"]:
                dns_record_id = None

                if dns_record["id"] is not None:
                    dns_record_id = dns_record["id"]
                else:
                    if self.dns_record_request is not None:
                        dns_record_request = self.dns_record_request
                    else:
                        # fetch dns record id
                        dns_record_request = get(
                            "https://api.cloudflare.com/client/v4/zones/{}/dns_records?type=A&name={}".format(zone_id, "{}.{}".format(dns_record["name"], url["name"])),
                            headers={
                                "X-Auth-Email": self.config["cloudflare_email"],
                                "X-Auth-Key": self.config["cloudflare_api_key"],
                                "Content-Type": "application/json"
                            })

                    for cf_dns_record in dns_record_request.json()["result"]:
                        dns_record_name = cf_dns_record["name"]

                        if dns_record_name != dns_record["name"] + "." + url["name"]:
                            continue

                        dns_record_id = cf_dns_record["id"]

                    if dns_record_id is None:
                        print("DNS Entry is not registered in Cloudflare")
                        print("Exiting...")
                        continue

                    # change dns record id in the config
                    dns_record["id"] = dns_record_id

                print("DNS Record id is {} for dns record {} on url {}".format(dns_record_id, dns_record["name"], url["name"]))

                # put the new ip address to the dns record
                rq = put(
                    "https://api.cloudflare.com/client/v4/zones/{}/dns_records/{}".format(zone_id, dns_record_id),
                    headers={
                        "X-Auth-Email": self.config["cloudflare_email"],
                        "X-Auth-Key": self.config["cloudflare_api_key"],
                        "Content-Type": "application/json"
                    },
                    json={
                        "content": ip,
                        "name": "{}.{}".format(dns_record["name"], url["name"]),
                        "proxied": False,
                        "type": "A",
                        "ttl": "1"
                    }
                )

                if rq.json()["success"]:
                    print(
                        "Successfully applied {} for ip {}".format("{}.{}".format(dns_record["name"], url["name"]), ip))
                else:
                    print("An Error occurred while updating the Domain name: {}".format(rq.json()["errors"]))

        # apply the new zone data to the urls
        self.config["ip"] = ip
        self.config["urls"] = urls
        self.update_config()
        print("All domains were updated or are up to date, rerunning in {} minute/s".format(self.config["sleep_time"]))

    def __init__(self):
        self.config = read_config()
        self.zone_id_request = None
        self.dns_record_request = None

        while True:
            self.run()
            time.sleep(self.config["sleep_time"] * 60)


main()
