import codecs, grpc, os, string
import rpc_pb2 as ln, rpc_pb2_grpc as lnrpc
LND_DIR = "/home/wamde/.lnd/"
macaroon = codecs.encode(open(LND_DIR + 'data/chain/bitcoin/mainnet/admin.macaroon', 'rb').read(), 'hex')
os.environ['GRPC_SSL_CIPHER_SUITES'] = 'HIGH+ECDSA'
cert = open(LND_DIR + 'tls.cert', 'rb').read()
ssl_creds = grpc.ssl_channel_credentials(cert)
channel_options = [
            ('grpc.max_message_length', 50 * 1024 * 1024),
            ('grpc.max_receive_message_length', 50 * 1024 * 1024)
        ]
channel = grpc.secure_channel('localhost:10009', ssl_creds, channel_options)


stub = lnrpc.LightningStub(channel)


def main():

	# header
	response = stub.GetInfo(ln.GetInfoRequest(), metadata=[('macaroon', macaroon)])
	alias = response.alias
	chain = response.chains[0]
	version = response.version

	channel_graph = get_channel_graph()

	header = "%s (%s, lnd %s)" % (alias, chain, version)

	print header


	# channels
	request = ln.ListChannelsRequest(
		active_only = True
		)
	response = stub.ListChannels(request, metadata=[('macaroon', macaroon)])
	channels = response.channels

	channel_number = 0
	channels_with_names = {}

	print "%d active channels" % (len(channels))
	max_capacity = max([c.capacity for c in channels])
	for channel in channels:
		channels_with_names[string.ascii_uppercase[channel_number]] = {"channel": channel}
		capacity = channel.capacity
		local_balance = channel.local_balance
		chan_id = channel.chan_id
		remote_pubkey = channel.remote_pubkey
		node_alias = get_node_alias(channel_graph, remote_pubkey)
		if len(node_alias) >= 15:
			node_alias = node_alias[:9] + "[...]"
		else:
			node_alias += " "*(15-1-len(node_alias))
		score = channel_score(capacity, local_balance)
                channels_with_names[string.ascii_uppercase[channel_number]]["score"] = score
		print (string.ascii_uppercase[channel_number] + "/ " + str(chan_id) + " "
			   + node_alias + " "
			   + channel_cursor(capacity, local_balance, max_capacity, score)
			   + " " + remote_pubkey)
		channel_number += 1

def channel_cursor(capacity, local_balance, max_capacity, score):
	max_capacity_digits = len("{:,}".format(max_capacity))
	num_steps = 60
	num_pluses = int(num_steps * float(local_balance) / float(capacity))
	cursor_string = "[" + "+"*num_pluses + "-"*(num_steps-num_pluses) + "]"
	balance_string = "(%d/%d sat)" % (local_balance, capacity)
	balance_string = "({local_balance:>{max_capacity_digits},} / {capacity:>{max_capacity_digits},}), score={score:.3f}".format(
		local_balance=local_balance, capacity=capacity,
		max_capacity_digits=max_capacity_digits,
		score=score
	)
	full_string = cursor_string + " " + balance_string
	return full_string

def channel_score(capacity, local_balance):
	fullness = float(local_balance) / float(capacity)
	return fullness  # there will be a better way but for now good enough

def get_channel_graph():
	request = ln.ChannelGraphRequest(
        include_unannounced=True,
    )
	response = stub.DescribeGraph(request, metadata=[('macaroon', macaroon)])
	return response

def get_node_alias(graph, pubkey):
	for p in graph.nodes:
		if p.pub_key == pubkey:
			return p.alias
	return ""

main()
